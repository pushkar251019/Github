"""Find + verify a decision-maker's email for free.

1. Prefer an address published on their own site that matches the person.
2. Otherwise generate common corporate patterns (first@, first.last@, flast@ ...).
3. Verify with DNS MX + an SMTP RCPT probe (no email is sent), and detect
   catch-all domains so we never claim "verified" when the server accepts anything.

Caveat: many home ISPs and cloud hosts block outbound port 25. Then status is
"unknown" and we fall back to the best pattern/published address, flagged as such.
"""
from __future__ import annotations

import random
import re
import smtplib
import socket
import string
import unicodedata

from . import net

GENERIC_PREFIXES = ("info", "hello", "contact", "office", "admin", "team", "support", "enquiries", "inquiries",
                    "mail", "sales", "reception", "frontdesk", "appointments", "booking", "bookings", "hi")
FREE_PROVIDERS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com", "live.com",
                  "msn.com", "protonmail.com", "proton.me", "gmx.com", "yandex.com", "zoho.com", "me.com"}


def ascii_slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def split_name(full: str) -> tuple[str, str]:
    full = re.sub(r"^(dr|mr|mrs|ms|miss|prof)\.?\s+", "", (full or "").strip(), flags=re.I)
    full = re.sub(r",?\s+(dds|dmd|md|phd|esq|cpa|jr|sr|ii|iii)\.?$", "", full, flags=re.I)
    parts = [p for p in re.split(r"\s+", full) if p and not re.fullmatch(r"[A-Z]\.?", p)]
    if not parts:
        return "", ""
    return parts[0], (parts[-1] if len(parts) > 1 else "")


def patterns(first: str, last: str, domain: str) -> list[str]:
    f, l = ascii_slug(first), ascii_slug(last)
    if not f:
        return []
    cands = [f"{f}"]
    if l:
        cands = [f"{f}", f"{f}.{l}", f"{f}{l}", f"{f[0]}{l}", f"{f[0]}.{l}", f"{f}{l[0]}", f"{f}_{l}",
                 f"{l}", f"{l}.{f}", f"{f}-{l}", f"{l}{f[0]}", f"{f[0]}{l[0]}"]
    seen, out = set(), []
    for c in cands:
        e = f"{c}@{domain}"
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def is_generic(email: str) -> bool:
    return email.split("@")[0].lower() in GENERIC_PREFIXES


def match_published(first: str, last: str, emails: list[str], domain: str) -> str | None:
    f, l = ascii_slug(first), ascii_slug(last)
    if not f:
        return None
    pats = set(patterns(first, last, domain))
    for e in emails:
        if e in pats:
            return e
    for e in emails:
        local = e.split("@")[0]
        if (l and l in local and local[0] == f[0]) or local == f:
            return e
    return None


class Verifier:
    def __init__(self, helo: str = "", mail_from: str = "", timeout: float = 10, ua: str = "ClientScout"):
        self.helo = helo or socket.getfqdn() or "localhost"
        self.mail_from = mail_from or f"verify@{self.helo if '.' in self.helo else 'example.com'}"
        self.timeout = timeout
        self.ua = ua
        self._mx: dict[str, list[str]] = {}
        self._catchall: dict[str, bool | None] = {}
        self.port25_blocked: bool | None = None

    def mx(self, domain: str) -> list[str]:
        if domain not in self._mx:
            try:
                self._mx[domain] = net.mx_records(domain, self.ua)
            except Exception:
                self._mx[domain] = []
        return self._mx[domain]

    def _rcpt(self, mx: str, addrs: list[str]) -> dict[str, int]:
        codes: dict[str, int] = {}
        with smtplib.SMTP(mx, 25, timeout=self.timeout) as s:
            s.helo(self.helo)
            s.mail(self.mail_from)
            for a in addrs:
                code, _ = s.rcpt(a)
                codes[a] = code
        return codes

    def probe(self, domain: str, addrs: list[str]) -> dict[str, int] | None:
        """RCPT codes for addrs (plus a random catch-all canary). None if we couldn't talk SMTP."""
        if self.port25_blocked:
            return None
        for host in self.mx(domain)[:2]:
            try:
                res = self._rcpt(host, addrs)
                self.port25_blocked = False
                return res
            except (socket.timeout, ConnectionRefusedError, OSError, smtplib.SMTPException):
                continue
        if self.port25_blocked is None:
            self.port25_blocked = True
        return None

    def verify_many(self, emails: list[str]) -> dict[str, str]:
        """Return {email: valid|invalid|catch_all|unknown|no_mx}."""
        out: dict[str, str] = {}
        by_dom: dict[str, list[str]] = {}
        for e in emails:
            by_dom.setdefault(e.split("@")[1].lower(), []).append(e.lower())
        for dom, addrs in by_dom.items():
            if not self.mx(dom):
                out.update({a: "no_mx" for a in addrs})
                continue
            canary = "zz" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12)) + "@" + dom
            codes = self.probe(dom, [canary] + addrs)
            if codes is None:
                out.update({a: "unknown" for a in addrs})
                continue
            catch_all = 200 <= codes.get(canary, 550) < 300
            self._catchall[dom] = catch_all
            for a in addrs:
                c = codes.get(a, 0)
                if catch_all and 200 <= c < 300:
                    out[a] = "catch_all"
                elif 200 <= c < 300:
                    out[a] = "valid"
                elif c in (550, 551, 553, 554):
                    out[a] = "invalid"
                else:
                    out[a] = "unknown"
        return out


RANK = {"valid": 0, "published": 1, "catch_all": 2, "unknown": 3, "no_mx": 8, "invalid": 9}


def find_best(first: str, last: str, domain: str, published: list[str], verifier: Verifier,
              probe: bool = True) -> dict:
    """Pick the best email for a person. Returns {email, status, source, tried}."""
    domain = domain.lower()
    if domain in FREE_PROVIDERS:
        domain = ""
    pub_match = match_published(first, last, published, domain) if domain else None
    cands = patterns(first, last, domain) if domain else []
    if pub_match and pub_match not in cands:
        cands.insert(0, pub_match)
    results: dict[str, str] = {}
    if probe and cands:
        results = verifier.verify_many(cands[:12])
        valid = [c for c in cands if results.get(c) == "valid"]
        if valid:
            pick = pub_match if pub_match in valid else valid[0]
            return {"email": pick, "status": "valid", "source": "published+smtp" if pick == pub_match else "pattern+smtp",
                    "tried": results}
        if any(v == "no_mx" for v in results.values()):
            return {"email": None, "status": "no_mx", "source": "", "tried": results}
    if pub_match and results.get(pub_match) != "invalid":
        return {"email": pub_match, "status": "published", "source": "website", "tried": results}
    # catch-all / unknown: most common SMB pattern first (first@ for owners of small firms, then first.last@)
    for c in cands:
        st = results.get(c, "unknown")
        if st in ("catch_all", "unknown"):
            return {"email": c, "status": st, "source": "pattern", "tried": results}
    generic = [e for e in published if is_generic(e)]
    if generic:
        return {"email": generic[0], "status": "generic", "source": "website", "tried": results}
    return {"email": None, "status": "not_found", "source": "", "tried": results}
