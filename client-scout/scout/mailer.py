"""Send through your own mailbox (SMTP) and read replies (IMAP), with guard-rails.

Guard-rails (enforced in code, not just in prompts):
  * suppression list (unsubscribes, bounces, manual) is checked before every send
  * daily cap, minimum gap + jitter between sends, sending window, weekdays only
  * opt-out line + physical address appended to every cold email (CAN-SPAM)
  * List-Unsubscribe header
  * correct threading headers so follow-ups and replies land in the same thread
"""
from __future__ import annotations

import email
import email.policy
import imaplib
import random
import re
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr, parsedate_to_datetime

from .config import secret
from .db import DB, now

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

UNSUB_RE = re.compile(r"\b(unsubscribe|remove me|take me off|stop emailing|do not (?:contact|email)|don'?t (?:contact|email)|"
                      r"no thanks|not interested|opt[- ]?out)\b", re.I)
BOUNCE_FROM = re.compile(r"(mailer-daemon|postmaster|mail delivery subsystem|delivery status)", re.I)
AUTO_REPLY = re.compile(r"(out of (?:the )?office|automatic reply|auto[- ]?reply|on vacation|away until|autoreply)", re.I)


def local_now(cfg: dict) -> datetime:
    tz = cfg["sending"].get("timezone")
    if tz and ZoneInfo:
        return datetime.now(ZoneInfo(tz))
    return datetime.now().astimezone()


def window_ok(cfg: dict, t: datetime | None = None) -> tuple[bool, str]:
    t = t or local_now(cfg)
    s = cfg["sending"]
    if s.get("weekdays_only", True) and t.weekday() >= 5:
        return False, "weekend (weekdays_only=true)"
    lo, hi = s.get("window_hours", [9, 17])
    if not (lo <= t.hour < hi):
        return False, f"outside sending window {lo}:00-{hi}:00 local (now {t:%H:%M})"
    return True, ""


def day_start_utc(cfg: dict) -> str:
    t = local_now(cfg)
    start = t.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def compose_body(cfg: dict, body: str, kind: str) -> str:
    """Append signature + compliance footer. Replies to a live conversation get the signature only."""
    s = cfg["sender"]
    body = body.rstrip()
    sig = (s.get("signature") or s.get("name") or "").strip()
    if sig and sig.splitlines()[0].strip() not in body[-200:]:
        body += "\n\n" + sig
    if kind in ("initial", "followup"):
        footer = []
        if cfg["sending"].get("opt_out_line"):
            footer.append(cfg["sending"]["opt_out_line"])
        if s.get("physical_address"):
            footer.append(s["physical_address"])
        if footer:
            body += "\n\n--\n" + "\n".join(footer)
    return body + "\n"


def build_message(cfg: dict, to_addr: str, subject: str, body: str, kind: str,
                  in_reply_to: str | None = None, refs: str | None = None) -> EmailMessage:
    s = cfg["sender"]
    from_addr = s.get("email") or cfg["smtp"].get("user")
    msg = EmailMessage(policy=email.policy.SMTP)
    msg["From"] = formataddr((s.get("name") or "", from_addr))
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=from_addr.split("@")[-1])
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = ((refs or "") + " " + in_reply_to).strip()
    if kind in ("initial", "followup"):
        msg["List-Unsubscribe"] = f"<mailto:{from_addr}?subject=unsubscribe>"
    msg.set_content(compose_body(cfg, body, kind))
    return msg


class Mailer:
    def __init__(self, cfg: dict, db: DB):
        self.cfg, self.db = cfg, db
        self._smtp: smtplib.SMTP | None = None

    def _connect(self) -> smtplib.SMTP:
        c = self.cfg["smtp"]
        pw = secret(c)
        if not (c.get("host") and c.get("user") and pw):
            raise RuntimeError(f"SMTP not configured: set smtp.host/smtp.user in scout.json and export {c.get('password_env')}")
        if c.get("ssl") or int(c.get("port", 587)) == 465:
            s = smtplib.SMTP_SSL(c["host"], int(c.get("port", 465)), timeout=30)
        else:
            s = smtplib.SMTP(c["host"], int(c.get("port", 587)), timeout=30)
            s.ehlo()
            if s.has_extn("starttls"):
                s.starttls()
                s.ehlo()
        s.login(c["user"], pw)
        return s

    def close(self):
        if self._smtp:
            try:
                self._smtp.quit()
            except Exception:
                pass
            self._smtp = None

    def can_send(self, ignore_window: bool = False) -> tuple[bool, str]:
        if not ignore_window:
            ok, why = window_ok(self.cfg)
            if not ok:
                return False, why
        limit = int(self.cfg["sending"].get("daily_limit", 30))
        sent = self.db.sent_today(day_start_utc(self.cfg))
        if sent >= limit:
            return False, f"daily limit reached ({sent}/{limit})"
        return True, ""

    def send_one(self, mid: int, dry_run: bool = False) -> tuple[bool, str]:
        m = self.db.message(mid)
        if not m or m["direction"] != "out" or m["status"] not in ("approved",):
            return False, "message is not an approved outbound draft"
        lead = self.db.lead(m["lead_id"])
        to = (m["to_addr"] or "").lower()
        if not to:
            return False, "no recipient"
        if self.db.is_suppressed(to):
            self.db.update_message(mid, status="skipped", error="suppressed")
            return False, f"{to} is on the suppression list"
        if lead["status"] in ("unsubscribed", "bounced", "lost", "booked") and m["kind"] != "reply":
            self.db.update_message(mid, status="skipped", error=f"lead is {lead['status']}")
            return False, f"lead is {lead['status']}"
        if m["kind"] == "followup":
            inbound = self.db.one("SELECT 1 FROM messages WHERE lead_id=? AND direction='in' AND classification IS NOT 'auto_reply' "
                                  "AND classification IS NOT 'bounce'", (lead["id"],))
            if inbound:
                self.db.update_message(mid, status="skipped", error="lead replied; follow-up cancelled")
                return False, "lead already replied - follow-up cancelled"
        msg = build_message(self.cfg, to, m["subject"], m["body"], m["kind"], m["in_reply_to"], m["refs"])
        if dry_run:
            return True, msg.as_string()
        try:
            if not self._smtp:
                self._smtp = self._connect()
            self._smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as e:
            self.db.update_message(mid, status="failed", error=str(e)[:300])
            self.db.suppress(to, "refused")
            self.db.update_lead(lead["id"], status="bounced")
            return False, f"recipient refused: {e}"
        except Exception as e:
            self.db.update_message(mid, status="failed", error=str(e)[:300])
            self.close()
            return False, f"send failed: {e}"
        self.db.update_message(mid, status="sent", sent_at=now(), message_id=msg["Message-ID"],
                               from_addr=self.cfg["sender"].get("email") or self.cfg["smtp"]["user"])
        if m["kind"] in ("initial", "followup") and lead["status"] in ("enriched", "queued", "qualified", "contacted"):
            self.db.update_lead(lead["id"], status="contacted")
        self.db.log(lead["id"], "sent", f"{m['kind']} step {m['step']} -> {to}")
        return True, msg["Message-ID"]

    def send_approved(self, max_n: int | None = None, dry_run: bool = False, ignore_window: bool = False,
                      sleep: bool = True, log=print) -> int:
        rows = self.db.q("SELECT id FROM messages WHERE direction='out' AND status='approved' "
                         "ORDER BY CASE kind WHEN 'reply' THEN 0 WHEN 'followup' THEN 1 ELSE 2 END, id")
        sent = 0
        gap = int(self.cfg["sending"].get("min_gap_seconds", 90))
        jitter = int(self.cfg["sending"].get("jitter_seconds", 60))
        for r in rows:
            if max_n is not None and sent >= max_n:
                break
            m = self.db.message(r["id"])
            # replies to people who wrote to us are conversations, not cold email: not limited by window
            ok, why = self.can_send(ignore_window=ignore_window or m["kind"] == "reply")
            if not ok and not dry_run:
                log(f"stopping: {why}")
                break
            if sleep and sent and not dry_run:
                time.sleep(gap + random.randint(0, max(jitter, 0)))
            good, info = self.send_one(r["id"], dry_run=dry_run)
            if good:
                sent += 1
                log(f"[{'DRY' if dry_run else 'SENT'}] msg {r['id']} -> {m['to_addr']}: {m['subject']}")
                if dry_run:
                    log(info)
            else:
                log(f"[SKIP] msg {r['id']}: {info}")
        self.close()
        return sent


# ---------------- IMAP ----------------

def _text_of(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                return part.get_content() if hasattr(part, "get_content") else part.get_payload(decode=True).decode("utf-8", "replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html = part.get_content()
                return re.sub(r"<[^>]+>", " ", html)
        return ""
    body = msg.get_content() if hasattr(msg, "get_content") else msg.get_payload()
    if msg.get_content_type() == "text/html":
        body = re.sub(r"<[^>]+>", " ", body)
    return body


def strip_quoted(text: str) -> str:
    lines, out = text.splitlines(), []
    for ln in lines:
        if re.match(r"^\s*>", ln):
            continue
        if re.match(r"^\s*On .{5,200} wrote:\s*$", ln) or re.match(r"^-{2,}\s*Original Message", ln, re.I) \
                or re.match(r"^\s*From:\s.+", ln) and out:
            break
        out.append(ln)
    return "\n".join(out).strip()


def parse_raw(raw: bytes) -> dict:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    name, addr = parseaddr(str(msg.get("From", "")))
    try:
        date = parsedate_to_datetime(str(msg.get("Date"))).astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        date = now()
    body = _text_of(msg) or ""
    return {
        "from_name": name, "from_addr": addr.lower(), "subject": str(msg.get("Subject", "")),
        "message_id": str(msg.get("Message-ID", "")).strip(), "in_reply_to": str(msg.get("In-Reply-To", "")).strip(),
        "refs": str(msg.get("References", "")).strip(), "date": date, "body": strip_quoted(body)[:8000],
        "full_body": body[:20000], "auto_submitted": str(msg.get("Auto-Submitted", "")).lower(),
    }


def classify_basic(p: dict) -> str | None:
    """Deterministic pre-classification. The agent does the nuanced read."""
    if BOUNCE_FROM.search(p["from_addr"] + " " + p["from_name"]) or "delivery status notification" in p["subject"].lower():
        return "bounce"
    if (p.get("auto_submitted") and p["auto_submitted"] != "no") or AUTO_REPLY.search(p["subject"]):
        return "auto_reply"
    if UNSUB_RE.search(p["body"][:500]) and len(p["body"]) < 600:
        return "unsubscribe"
    return None


def bounced_address(p: dict) -> str | None:
    m = re.search(r"(?:Final-Recipient|Original-Recipient):\s*rfc822;\s*(\S+@\S+)", p["full_body"], re.I)
    if m:
        return m.group(1).strip("<>").lower()
    m = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", p["full_body"])
    return m.group(1).lower() if m else None


def match_lead(db: DB, p: dict) -> tuple[int | None, dict | None]:
    ids = re.findall(r"<[^>]+>", p["in_reply_to"] + " " + p["refs"])
    for mid in reversed(ids):
        r = db.one("SELECT * FROM messages WHERE message_id=? AND direction='out'", (mid,))
        if r:
            return r["lead_id"], dict(r)
    r = db.one("SELECT * FROM messages WHERE to_addr=? AND direction='out' AND status='sent' ORDER BY id DESC LIMIT 1",
               (p["from_addr"],))
    if r:
        return r["lead_id"], dict(r)
    c = db.one("SELECT lead_id FROM contacts WHERE email=?", (p["from_addr"],))
    if c:
        return c["lead_id"], None
    dom = p["from_addr"].split("@")[-1]
    l = db.one("SELECT id FROM leads WHERE domain=? AND status IN ('contacted','replied','interested')", (dom,))
    return (l["id"], None) if l else (None, None)


def ingest(db: DB, raw: bytes, uid: str = "") -> dict | None:
    p = parse_raw(raw)
    if p["message_id"] and db.one("SELECT 1 FROM messages WHERE message_id=? AND direction='in'", (p["message_id"],)):
        return None
    cls = classify_basic(p)
    if cls == "bounce":
        addr = bounced_address(p)
        r = db.one("SELECT * FROM messages WHERE to_addr=? AND direction='out' ORDER BY id DESC LIMIT 1", (addr,)) if addr else None
        if not r:
            return None
        db.suppress(addr, "bounce")
        db.update_lead(r["lead_id"], status="bounced")
        db.add_message(lead_id=r["lead_id"], direction="in", kind="inbound", from_addr=p["from_addr"], subject=p["subject"],
                       body=p["body"][:2000], message_id=p["message_id"], status="handled", classification="bounce",
                       imap_uid=uid, sent_at=p["date"])
        return {"lead_id": r["lead_id"], "classification": "bounce", **p}
    lead_id, parent = match_lead(db, p)
    if not lead_id:
        return None  # not a prospect conversation; leave the rest of the inbox alone
    mid = db.add_message(lead_id=lead_id, direction="in", kind="inbound", from_addr=p["from_addr"], subject=p["subject"],
                         body=p["body"], message_id=p["message_id"], in_reply_to=p["in_reply_to"], refs=p["refs"],
                         status="received" if cls != "auto_reply" else "handled", classification=cls, imap_uid=uid,
                         sent_at=p["date"])
    # cancel pending follow-ups once a human replies
    if cls != "auto_reply":
        db.x("UPDATE messages SET status='skipped', error='lead replied' WHERE lead_id=? AND kind='followup' "
             "AND status IN ('draft','approved')", (lead_id,))
        lead = db.lead(lead_id)
        if cls == "unsubscribe":
            db.suppress(p["from_addr"], "unsubscribe")
            db.update_lead(lead_id, status="unsubscribed")
            db.update_message(mid, status="handled")
        elif lead["status"] in ("contacted", "queued", "enriched"):
            db.update_lead(lead_id, status="replied")
    return {"id": mid, "lead_id": lead_id, "classification": cls, **p}


def sync_inbox(cfg: dict, db: DB, days: int = 14, log=print) -> list[dict]:
    c = cfg["imap"]
    pw = secret(c)
    if not (c.get("host") and c.get("user") and pw):
        raise RuntimeError(f"IMAP not configured: set imap.host/imap.user and export {c.get('password_env')}")
    box = imaplib.IMAP4_SSL(c["host"], int(c.get("port", 993)))
    box.login(c["user"], pw)
    new: list[dict] = []
    try:
        box.select(c.get("folder") or "INBOX", readonly=True)
        since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        last_uid = int(db.get_kv("imap_last_uid", 0) or 0)
        typ, data = box.uid("search", None, f"(SINCE {since})")
        uids = [int(u) for u in (data[0] or b"").split() if int(u) > last_uid]
        for uid in uids:
            typ, msg_data = box.uid("fetch", str(uid), "(BODY.PEEK[])")
            raw = next((part[1] for part in msg_data if isinstance(part, tuple)), None)
            if raw:
                res = ingest(db, raw, str(uid))
                if res:
                    new.append(res)
            db.set_kv("imap_last_uid", uid)
    finally:
        try:
            box.logout()
        except Exception:
            pass
    log(f"inbox: {len(new)} new prospect message(s)")
    return new
