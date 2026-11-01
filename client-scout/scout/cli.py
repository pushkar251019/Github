"""`scout` command line. The agent drives this; you can too."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__, config, emailfind, listings, mailer, net, site
from .db import STATUSES, open_db


def _out(obj, as_json: bool):
    if as_json:
        print(json.dumps(obj, indent=2, default=str))
        return True
    return False


def _row(r) -> dict:
    return dict(r) if r is not None else {}


def _ctx(args):
    cfg = config.load()
    return cfg, open_db(cfg)


def _body(args) -> str:
    if getattr(args, "body_file", None):
        return Path(args.body_file).read_text()
    if getattr(args, "body", None):
        return args.body
    if not sys.stdin.isatty():
        return sys.stdin.read()
    sys.exit("provide --body, --body-file or pipe the body on stdin")


# ---------------------------------------------------------------- setup
def cmd_init(args):
    home = Path.cwd()
    tgt = home / "scout.json"
    if not tgt.exists():
        shutil.copy(Path(__file__).resolve().parent.parent / "scout.example.json", tgt)
        print(f"created {tgt} - fill it in (or run /scout-setup in Claude Code)")
    cfg = config.load(home)
    open_db(cfg)
    print(f"database ready at {config.data_dir(cfg) / 'scout.db'}")


def cmd_doctor(args):
    cfg, db = _ctx(args)
    ok = lambda b: "OK " if b else "-- "
    print(f"client-scout {__version__}  home={cfg['_home']}")
    print(ok(Path(cfg["_path"]).exists()), "scout.json present")
    print(ok(bool(cfg["business"].get("description"))), "business profile filled (run /scout-setup)")
    print(ok((Path(cfg["_home"]) / "icp.md").exists()), "icp.md built (run /scout-icp)")
    print(ok(bool(cfg["sender"].get("booking_link"))), "booking link set")
    print(ok(bool(cfg["sender"].get("physical_address"))), "physical address set (required by CAN-SPAM)")
    pw = config.secret(cfg["smtp"])
    print(ok(bool(cfg["smtp"].get("user") and pw)), f"SMTP credentials (user + ${cfg['smtp']['password_env']})")
    if args.network:
        ua = config.user_agent(cfg)
        r = net.fetch("https://nominatim.openstreetmap.org/status.php?format=json", ua, check_robots=False)
        print(ok(r.ok), "OpenStreetMap reachable")
        mx = net.mx_records("gmail.com", ua)
        print(ok(bool(mx)), "DNS MX lookup works")
        v = emailfind.Verifier(cfg["verify"].get("helo_host"), cfg["verify"].get("mail_from"), 8, ua)
        v.probe("gmail.com", ["postmaster@gmail.com"])
        print(ok(v.port25_blocked is False), "outbound port 25 open (SMTP verification) - if blocked, emails are marked 'unknown'")
        if cfg["smtp"].get("user") and pw:
            try:
                m = mailer.Mailer(cfg, db)
                m._smtp = m._connect()
                m.close()
                print("OK ", "SMTP login")
            except Exception as e:
                print("-- ", f"SMTP login failed: {e}")


def cmd_config(args):
    cfg = config.load()
    if args.set:
        for kv in args.set:
            key, _, val = kv.partition("=")
            try:
                val = json.loads(val)
            except Exception:
                pass
            node = cfg
            parts = key.split(".")
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = val
        config.save(cfg)
    print(json.dumps({k: v for k, v in cfg.items() if not k.startswith("_")}, indent=2))


# ---------------------------------------------------------------- discovery
def cmd_industries(args):
    for k, v in listings.INDUSTRY_TAGS.items():
        print(f"{k:20s} {', '.join(v)}")


def cmd_find(args):
    cfg, db = _ctx(args)
    ua = config.user_agent(cfg)
    leads = listings.search(args.industry, args.city, ua, radius_km=args.radius, tags=args.tag,
                            name_regex=args.name, require_website=not args.include_no_website,
                            skip_chains=not args.include_chains)
    created = 0
    for lead in leads[: args.limit]:
        _, new = db.upsert_lead(lead)
        created += new
    print(f"found {len(leads)} businesses for {args.industry!r} near {args.city!r}; {created} new leads added")


def cmd_add(args):
    cfg, db = _ctx(args)
    site_url = net.normalize_url(args.website or "")
    lid, new = db.upsert_lead({"name": args.name, "website": site_url, "domain": net.domain_of(site_url) if site_url else None,
                               "phone": args.phone, "email": args.email, "address": args.address, "city": args.city,
                               "industry": args.industry, "source": args.source or "manual",
                               "source_ref": args.ref, "notes": args.notes})
    print(json.dumps({"id": lid, "created": new}))


def cmd_import(args):
    cfg, db = _ctx(args)
    rows = listings.read_csv(args.file, args.industry or "", args.city or "")
    created = sum(db.upsert_lead(r)[1] for r in rows)
    print(f"imported {created} new leads ({len(rows)} rows read)")


# ---------------------------------------------------------------- analysis
def cmd_analyze(args):
    cfg, db = _ctx(args)
    ua = config.user_agent(cfg)
    ids = args.ids or [r["id"] for r in db.leads(status=args.status, limit=args.limit)]
    for lid in ids:
        lead = db.lead(lid)
        if not lead["website"]:
            db.update_lead(lid, status="disqualified", fit_reason="no website")
            print(f"#{lid} {lead['name']}: no website -> disqualified")
            continue
        data, text = site.analyze(lead["website"], ua, lead["name"], cfg["discovery"].get("country", "US"),
                                  respect_robots=cfg["discovery"].get("respect_robots", True),
                                  delay=float(cfg["discovery"].get("request_delay", 1.0)))
        db.save_site(lid, data, text)
        if not data.get("reachable"):
            db.update_lead(lid, status="disqualified", fit_reason=f"website unreachable ({data.get('status')})")
            print(f"#{lid} {lead['name']}: site unreachable")
            continue
        upd = {"status": "analyzed"}
        if data.get("domain") and data["domain"] != lead["domain"]:
            upd["domain"] = data["domain"]
        db.update_lead(lid, **upd)
        print(f"#{lid} {lead['name']}: {len(data['emails'])} emails, {len(data['people'])} people, "
              f"signals={','.join(data['signals']) or '-'}")


def cmd_leads(args):
    cfg, db = _ctx(args)
    rows = [_row(r) for r in db.leads(args.status, args.limit, args.industry, args.city)]
    if _out(rows, args.json):
        return
    for r in rows:
        print(f"#{r['id']:<5} {r['status']:<12} {str(r['score'] or ''):>3}  {r['name'][:38]:<38} {r['domain'] or '':<28} {r['city'] or ''}")
    print(f"({len(rows)} shown)")


def cmd_show(args):
    cfg, db = _ctx(args)
    lead = db.lead(args.id)
    if not lead:
        sys.exit("no such lead")
    data, text = db.site(args.id)
    obj = {"lead": _row(lead), "site": data, "contacts": [_row(c) for c in db.contacts(args.id)],
           "thread": [_row(m) for m in db.thread(args.id)]}
    if args.text:
        obj["site_text"] = text[: args.text_chars]
    print(json.dumps(obj, indent=2, default=str))


def cmd_qualify(args):
    cfg, db = _ctx(args)
    db.update_lead(args.id, status="qualified" if args.score >= args.threshold else "disqualified",
                   score=args.score, fit_reason=args.reason, hook=args.hook)
    print(f"#{args.id} score={args.score} -> {db.lead(args.id)['status']}")


def cmd_disqualify(args):
    cfg, db = _ctx(args)
    db.update_lead(args.id, status="disqualified", fit_reason=args.reason, score=args.score)
    print(f"#{args.id} disqualified")


def cmd_set(args):
    cfg, db = _ctx(args)
    fields = {}
    for kv in args.fields:
        k, _, v = kv.partition("=")
        fields[k] = v
    if args.status:
        fields["status"] = args.status
    db.update_lead(args.id, **fields)
    if args.status in ("unsubscribed", "bounced"):
        c = db.primary_contact(args.id)
        if c and c["email"]:
            db.suppress(c["email"], args.status)
    print(json.dumps(_row(db.lead(args.id)), default=str))


# ---------------------------------------------------------------- contacts / email
def cmd_contact(args):
    cfg, db = _ctx(args)
    first, last = args.first, args.last
    if args.name and not first:
        first, last = emailfind.split_name(args.name)
    cid = db.add_contact(args.id, first or "", last or "", args.role or "", args.email or "",
                         args.email_status or ("provided" if args.email else ""), args.source or "agent")
    print(json.dumps({"contact_id": cid}))


def cmd_findemail(args):
    cfg, db = _ctx(args)
    ua = config.user_agent(cfg)
    v = emailfind.Verifier(cfg["verify"].get("helo_host"), cfg["verify"].get("mail_from"),
                           float(cfg["verify"].get("timeout", 10)), ua)
    ids = args.ids or [r["id"] for r in db.leads(status="qualified", limit=args.limit)]
    results = []
    for lid in ids:
        lead = db.lead(lid)
        data, _ = db.site(lid)
        c = db.primary_contact(lid)
        published = list(dict.fromkeys((data.get("emails") or []) + ([lead["email"]] if lead["email"] else [])))
        domain = lead["domain"] or data.get("domain") or ""
        if c and (c["first"] or c["last"]):
            res = emailfind.find_best(c["first"], c["last"], domain, published, v,
                                      probe=cfg["verify"].get("smtp_probe", True) and not args.no_probe)
        else:
            gen = [e for e in published if emailfind.is_generic(e)] or published
            res = {"email": gen[0] if gen else None, "status": "generic" if gen else "not_found", "source": "website", "tried": {}}
        if res["email"]:
            if c:
                db.x("UPDATE contacts SET email=?, email_status=?, email_source=? WHERE id=?",
                     (res["email"], res["status"], res["source"], c["id"]))
            else:
                db.add_contact(lid, email=res["email"], email_status=res["status"], email_source=res["source"])
            db.update_lead(lid, status="enriched")
        else:
            db.update_lead(lid, status="no_email")
        results.append({"id": lid, "name": lead["name"], **{k: res[k] for k in ("email", "status", "source")}})
        print(f"#{lid} {lead['name']}: {res['email'] or '-'} [{res['status']}]")
    if v.port25_blocked:
        print("note: outbound port 25 is blocked here, so SMTP verification was skipped (status 'unknown'/'published').")
    if args.json:
        print(json.dumps(results, indent=2))


def cmd_verify(args):
    cfg, db = _ctx(args)
    v = emailfind.Verifier(cfg["verify"].get("helo_host"), cfg["verify"].get("mail_from"),
                           float(cfg["verify"].get("timeout", 10)), config.user_agent(cfg))
    print(json.dumps(v.verify_many(args.emails), indent=2))


# ---------------------------------------------------------------- drafting / sending
def cmd_draft(args):
    cfg, db = _ctx(args)
    lead = db.lead(args.id)
    c = db.primary_contact(args.id)
    to = args.to or (c["email"] if c else None) or lead["email"]
    if not to:
        sys.exit("no recipient email for this lead; run findemail or pass --to")
    if db.is_suppressed(to):
        sys.exit(f"{to} is suppressed - not drafting")
    in_reply_to = refs = None
    subject = args.subject
    if args.kind in ("followup", "reply"):
        prev = db.one("SELECT * FROM messages WHERE lead_id=? AND message_id IS NOT NULL AND message_id!='' "
                      "ORDER BY COALESCE(sent_at,created_at) DESC, id DESC LIMIT 1", (args.id,))
        if prev:
            in_reply_to, refs = prev["message_id"], prev["refs"]
            if not subject:
                s = prev["subject"] or ""
                subject = s if s.lower().startswith("re:") else f"Re: {s}"
    if not subject:
        sys.exit("--subject is required for an initial email")
    step = args.step
    if step is None:
        step = db.one("SELECT COUNT(*) n FROM messages WHERE lead_id=? AND direction='out' AND kind IN ('initial','followup') "
                      "AND status IN ('sent','approved','draft')", (args.id,))["n"]
    status = "approved" if args.approve else "draft"
    mid = db.add_message(lead_id=args.id, contact_id=c["id"] if c else None, direction="out", kind=args.kind, step=step,
                         to_addr=to.lower(), subject=subject, body=_body(args), in_reply_to=in_reply_to, refs=refs,
                         status=status)
    if args.kind == "initial" and lead["status"] in ("enriched", "qualified"):
        db.update_lead(args.id, status="queued")
    if args.reply_to:
        db.update_message(args.reply_to, status="handled", classification=args.classification or None)
    print(json.dumps({"message_id": mid, "status": status, "to": to, "subject": subject}))


def cmd_queue(args):
    cfg, db = _ctx(args)
    rows = db.q("SELECT m.*, l.name FROM messages m JOIN leads l ON l.id=m.lead_id WHERE m.direction='out' AND m.status IN (%s) "
                "ORDER BY m.id" % ",".join("?" * len(args.status.split(","))), args.status.split(","))
    if _out([_row(r) for r in rows], args.json):
        return
    for r in rows:
        print(f"--- msg {r['id']} [{r['status']}] {r['kind']} step {r['step']} | lead #{r['lead_id']} {r['name']}\n"
              f"To: {r['to_addr']}\nSubject: {r['subject']}\n\n{r['body'].strip()}\n")
    print(f"({len(rows)} messages)")


def cmd_approve(args):
    cfg, db = _ctx(args)
    if args.all:
        db.x("UPDATE messages SET status='approved' WHERE direction='out' AND status='draft'")
        print("approved all drafts")
        return
    for mid in args.ids:
        db.update_message(mid, status="approved")
    print(f"approved {len(args.ids)}")


def cmd_edit(args):
    cfg, db = _ctx(args)
    fields = {}
    if args.subject:
        fields["subject"] = args.subject
    if args.body or args.body_file:
        fields["body"] = _body(args)
    if args.discard:
        fields["status"] = "skipped"
    db.update_message(args.mid, **fields)
    print(json.dumps(_row(db.message(args.mid)), default=str))


def cmd_send(args):
    cfg, db = _ctx(args)
    m = mailer.Mailer(cfg, db)
    n = m.send_approved(max_n=args.max, dry_run=args.dry_run, ignore_window=args.now, sleep=not args.no_sleep)
    print(f"{'would send' if args.dry_run else 'sent'} {n} message(s)")


def cmd_inbox(args):
    cfg, db = _ctx(args)
    if args.file:
        res = [r for f in args.file if (r := mailer.ingest(db, Path(f).read_bytes()))]
    else:
        res = mailer.sync_inbox(cfg, db, days=args.days)
    pending = db.q("SELECT m.*, l.name, l.status lead_status FROM messages m JOIN leads l ON l.id=m.lead_id "
                   "WHERE m.direction='in' AND m.status='received' ORDER BY m.id")
    if _out({"new": [{k: r[k] for k in ("lead_id", "classification", "from_addr", "subject")} for r in res],
             "needs_response": [_row(r) for r in pending]}, args.json):
        return
    for r in pending:
        print(f"--- inbound msg {r['id']} | lead #{r['lead_id']} {r['name']} ({r['lead_status']})  hint={r['classification'] or '-'}\n"
              f"From: {r['from_addr']}\nSubject: {r['subject']}\n\n{r['body'].strip()[:1500]}\n")
    print(f"{len(pending)} conversation(s) need a response")


def cmd_handled(args):
    cfg, db = _ctx(args)
    db.update_message(args.mid, status="handled", classification=args.classification)
    print("ok")


def cmd_thread(args):
    cfg, db = _ctx(args)
    for m in db.thread(args.id):
        arrow = ">>" if m["direction"] == "out" else "<<"
        print(f"{arrow} [{m['status']}] {m['sent_at'] or m['created_at']} {m['kind']} {m['subject']}\n{(m['body'] or '').strip()}\n")


def cmd_due(args):
    """Leads whose sequence needs the next follow-up drafted."""
    cfg, db = _ctx(args)
    days = cfg["sequence"].get("followup_days", [3, 7, 14])
    max_f = int(cfg["sequence"].get("max_followups", len(days)))
    now = datetime.now(timezone.utc)
    due = []
    for lead in db.q("SELECT * FROM leads WHERE status='contacted'"):
        msgs = db.thread(lead["id"])
        if any(m["direction"] == "in" and m["classification"] not in ("auto_reply", "bounce") for m in msgs):
            continue
        if any(m["direction"] == "out" and m["status"] in ("draft", "approved") for m in msgs):
            continue
        outs = [m for m in msgs if m["direction"] == "out" and m["status"] == "sent" and m["kind"] in ("initial", "followup")]
        if not outs:
            continue
        first = min(datetime.fromisoformat(m["sent_at"]) for m in outs)
        n_follow = len(outs) - 1
        if n_follow >= max_f or n_follow >= len(days):
            if (now - first).days >= days[-1] + 7:
                db.update_lead(lead["id"], status="lost", fit_reason=(lead["fit_reason"] or "") + " | sequence finished, no reply")
            continue
        if now >= first + timedelta(days=days[n_follow]):
            due.append({"id": lead["id"], "name": lead["name"], "followup_number": n_follow + 1,
                        "days_since_first": (now - first).days, "to": outs[-1]["to_addr"]})
    if _out(due, args.json):
        return
    for d in due:
        print(f"#{d['id']} {d['name']}: follow-up {d['followup_number']} due ({d['days_since_first']}d since first email)")
    print(f"{len(due)} follow-up(s) due")


def cmd_suppress(args):
    cfg, db = _ctx(args)
    for v in args.values:
        db.suppress(v, args.reason or "manual")
    print(f"suppressed {len(args.values)}")


def cmd_stats(args):
    cfg, db = _ctx(args)
    by = {r["status"]: r["n"] for r in db.q("SELECT status, COUNT(*) n FROM leads GROUP BY status")}
    sent = db.one("SELECT COUNT(*) n FROM messages WHERE direction='out' AND status='sent'")["n"]
    inbound = db.one("SELECT COUNT(DISTINCT lead_id) n FROM messages WHERE direction='in' AND COALESCE(classification,'') "
                     "NOT IN ('bounce','auto_reply')")["n"]
    contacted = db.one("SELECT COUNT(DISTINCT lead_id) n FROM messages WHERE direction='out' AND status='sent'")["n"]
    today = db.sent_today(mailer.day_start_utc(cfg))
    obj = {"leads_by_status": {s: by.get(s, 0) for s in STATUSES if by.get(s)}, "emails_sent": sent,
           "sent_today": today, "daily_limit": cfg["sending"]["daily_limit"], "leads_contacted": contacted,
           "leads_replied": inbound, "reply_rate": round(inbound / contacted, 3) if contacted else None,
           "booked": by.get("booked", 0),
           "drafts_waiting": db.one("SELECT COUNT(*) n FROM messages WHERE status='draft'")["n"],
           "approved_waiting": db.one("SELECT COUNT(*) n FROM messages WHERE status='approved'")["n"],
           "replies_needing_response": db.one("SELECT COUNT(*) n FROM messages WHERE direction='in' AND status='received'")["n"]}
    if _out(obj, args.json):
        return
    for k, v in obj.items():
        print(f"{k:28s} {v}")


def cmd_export(args):
    cfg, db = _ctx(args)
    rows = db.q("SELECT l.*, c.first, c.last, c.role, c.email AS contact_email, c.email_status FROM leads l "
                "LEFT JOIN contacts c ON c.lead_id=l.id AND c.is_primary=1 ORDER BY l.id")
    out = Path(args.out)
    with out.open("w", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            for r in rows:
                w.writerow(dict(r))
    print(f"wrote {len(rows)} rows to {out}")


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scout", description="Client Scout - free AI sales rep toolkit")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        return sp

    add("init", cmd_init, "create scout.json + database in the current folder")
    sp = add("doctor", cmd_doctor, "check configuration"); sp.add_argument("--network", action="store_true")
    sp = add("config", cmd_config, "show or set config values"); sp.add_argument("--set", nargs="*", help="key.path=value")

    add("industries", cmd_industries, "list built-in industry -> OpenStreetMap tag mappings")
    sp = add("find", cmd_find, "discover businesses from OpenStreetMap")
    sp.add_argument("--industry", required=True); sp.add_argument("--city", required=True)
    sp.add_argument("--radius", type=float, default=10, help="km"); sp.add_argument("--limit", type=int, default=100)
    sp.add_argument("--tag", action="append", help="extra OSM tag key=value"); sp.add_argument("--name", help="name regex filter")
    sp.add_argument("--include-no-website", action="store_true"); sp.add_argument("--include-chains", action="store_true")
    sp = add("add", cmd_add, "add one business (e.g. found via web search)")
    sp.add_argument("--name", required=True)
    for f in ("website", "phone", "email", "address", "city", "industry", "source", "ref", "notes"):
        sp.add_argument(f"--{f}")
    sp = add("import", cmd_import, "import a CSV of businesses")
    sp.add_argument("file"); sp.add_argument("--industry"); sp.add_argument("--city")

    sp = add("analyze", cmd_analyze, "analyse websites (contacts, people, ad pixels, tech, health)")
    sp.add_argument("ids", nargs="*", type=int); sp.add_argument("--status", default="new"); sp.add_argument("--limit", type=int, default=25)
    sp = add("leads", cmd_leads, "list leads")
    sp.add_argument("--status"); sp.add_argument("--industry"); sp.add_argument("--city")
    sp.add_argument("--limit", type=int, default=50); sp.add_argument("--json", action="store_true")
    sp = add("show", cmd_show, "full lead record as JSON")
    sp.add_argument("id", type=int); sp.add_argument("--text", action="store_true", help="include website text")
    sp.add_argument("--text-chars", type=int, default=8000)
    sp = add("qualify", cmd_qualify, "record AI fit score (>= threshold => qualified)")
    sp.add_argument("id", type=int); sp.add_argument("--score", type=int, required=True)
    sp.add_argument("--reason", required=True); sp.add_argument("--hook", help="the specific personalisation angle")
    sp.add_argument("--threshold", type=int, default=70)
    sp = add("disqualify", cmd_disqualify, "mark not a fit")
    sp.add_argument("id", type=int); sp.add_argument("--reason", required=True); sp.add_argument("--score", type=int)
    sp = add("set", cmd_set, "set lead fields / status")
    sp.add_argument("id", type=int); sp.add_argument("--status", choices=STATUSES); sp.add_argument("fields", nargs="*", help="field=value")

    sp = add("contact", cmd_contact, "add decision-maker for a lead")
    sp.add_argument("id", type=int); sp.add_argument("--name"); sp.add_argument("--first"); sp.add_argument("--last")
    sp.add_argument("--role"); sp.add_argument("--email"); sp.add_argument("--email-status"); sp.add_argument("--source")
    sp = add("findemail", cmd_findemail, "find + verify the primary contact's email")
    sp.add_argument("ids", nargs="*", type=int); sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--no-probe", action="store_true"); sp.add_argument("--json", action="store_true")
    sp = add("verify", cmd_verify, "verify arbitrary email addresses"); sp.add_argument("emails", nargs="+")

    sp = add("draft", cmd_draft, "store an email draft (body via --body/--body-file/stdin)")
    sp.add_argument("id", type=int); sp.add_argument("--kind", choices=["initial", "followup", "reply"], default="initial")
    sp.add_argument("--subject"); sp.add_argument("--body"); sp.add_argument("--body-file"); sp.add_argument("--to")
    sp.add_argument("--step", type=int); sp.add_argument("--approve", action="store_true")
    sp.add_argument("--reply-to", type=int, help="inbound message id this answers (marks it handled)")
    sp.add_argument("--classification", help="classification of the inbound message being answered")
    sp = add("queue", cmd_queue, "show drafts/approved messages")
    sp.add_argument("--status", default="draft"); sp.add_argument("--json", action="store_true")
    sp = add("approve", cmd_approve, "approve drafts for sending")
    sp.add_argument("ids", nargs="*", type=int); sp.add_argument("--all", action="store_true")
    sp = add("edit", cmd_edit, "edit or discard a draft")
    sp.add_argument("mid", type=int); sp.add_argument("--subject"); sp.add_argument("--body"); sp.add_argument("--body-file")
    sp.add_argument("--discard", action="store_true")
    sp = add("send", cmd_send, "send approved messages within limits")
    sp.add_argument("--max", type=int); sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--now", action="store_true", help="ignore sending window (daily cap still applies)")
    sp.add_argument("--no-sleep", action="store_true", help="don't wait between sends (testing only)")
    sp = add("inbox", cmd_inbox, "pull replies over IMAP and list conversations needing a response")
    sp.add_argument("--days", type=int, default=14); sp.add_argument("--json", action="store_true")
    sp.add_argument("--file", nargs="*", help="ingest .eml files instead of IMAP (testing / Gmail-MCP exports)")
    sp = add("handled", cmd_handled, "mark an inbound message handled without replying")
    sp.add_argument("mid", type=int); sp.add_argument("--classification", required=True)
    sp = add("thread", cmd_thread, "print conversation with a lead"); sp.add_argument("id", type=int)
    sp = add("due", cmd_due, "list follow-ups that are due"); sp.add_argument("--json", action="store_true")
    sp = add("suppress", cmd_suppress, "never email these addresses/@domains")
    sp.add_argument("values", nargs="+"); sp.add_argument("--reason")
    sp = add("stats", cmd_stats, "pipeline dashboard"); sp.add_argument("--json", action="store_true")
    sp = add("export", cmd_export, "export leads + contacts to CSV"); sp.add_argument("--out", default="leads.csv")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except (RuntimeError, ValueError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
