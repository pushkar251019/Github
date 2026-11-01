"""SQLite CRM: leads, site analysis, contacts, messages, suppression, events."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

STATUSES = [
    "new",           # discovered, not yet analysed
    "analyzed",      # website analysed, awaiting AI qualification
    "qualified",     # fits the ICP
    "disqualified",  # does not fit
    "enriched",      # decision-maker + email found
    "queued",        # first email drafted / approved
    "contacted",     # first email sent, sequence running
    "replied",       # they replied, conversation open
    "interested",    # positive intent
    "booked",        # call booked  (win)
    "lost",          # explicit no / dead
    "unsubscribed",  # opted out
    "bounced",       # undeliverable
    "no_email",      # qualified but no reachable email
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  domain TEXT,
  website TEXT,
  phone TEXT,
  email TEXT,
  address TEXT,
  city TEXT,
  industry TEXT,
  lat REAL, lon REAL,
  source TEXT,
  source_ref TEXT UNIQUE,
  status TEXT NOT NULL DEFAULT 'new',
  score INTEGER,
  fit_reason TEXT,
  hook TEXT,
  notes TEXT,
  created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS leads_domain ON leads(domain);
CREATE TABLE IF NOT EXISTS site_data (
  lead_id INTEGER PRIMARY KEY REFERENCES leads(id) ON DELETE CASCADE,
  data TEXT, text TEXT, analyzed_at TEXT
);
CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY,
  lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
  first TEXT, last TEXT, role TEXT,
  email TEXT, email_status TEXT, email_source TEXT,
  is_primary INTEGER DEFAULT 0,
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS contacts_email ON contacts(email);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY,
  lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
  contact_id INTEGER,
  direction TEXT,             -- out | in
  kind TEXT,                  -- initial | followup | reply | inbound
  step INTEGER DEFAULT 0,
  to_addr TEXT, from_addr TEXT,
  subject TEXT, body TEXT,
  message_id TEXT, in_reply_to TEXT, refs TEXT,
  status TEXT,                -- draft | approved | sent | failed | received | handled | skipped
  classification TEXT,
  error TEXT,
  imap_uid TEXT,
  created_at TEXT, sent_at TEXT
);
CREATE INDEX IF NOT EXISTS messages_lead ON messages(lead_id);
CREATE INDEX IF NOT EXISTS messages_mid ON messages(message_id);
CREATE TABLE IF NOT EXISTS suppression (
  value TEXT PRIMARY KEY,     -- email address or @domain
  reason TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, lead_id INTEGER, kind TEXT, detail TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DB:
    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)

    # ---- generic
    def q(self, sql: str, args=()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, args).fetchall()

    def one(self, sql: str, args=()):
        return self.conn.execute(sql, args).fetchone()

    def x(self, sql: str, args=()) -> int:
        cur = self.conn.execute(sql, args)
        self.conn.commit()
        return cur.lastrowid

    def log(self, lead_id, kind: str, detail: str = "") -> None:
        self.x("INSERT INTO events(lead_id,kind,detail,created_at) VALUES(?,?,?,?)", (lead_id, kind, detail, now()))

    def get_kv(self, k: str, default=None):
        r = self.one("SELECT v FROM kv WHERE k=?", (k,))
        return json.loads(r["v"]) if r else default

    def set_kv(self, k: str, v) -> None:
        self.x("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))

    # ---- leads
    def upsert_lead(self, lead: dict) -> tuple[int, bool]:
        """Insert unless the same source_ref or domain already exists. Returns (id, created)."""
        ref = lead.get("source_ref")
        if ref:
            r = self.one("SELECT id FROM leads WHERE source_ref=?", (ref,))
            if r:
                return r["id"], False
        dom = lead.get("domain")
        if dom:
            r = self.one("SELECT id FROM leads WHERE domain=?", (dom,))
            if r:
                return r["id"], False
        cols = ["name", "domain", "website", "phone", "email", "address", "city", "industry",
                "lat", "lon", "source", "source_ref", "notes"]
        vals = [lead.get(c) for c in cols]
        lid = self.x(f"INSERT INTO leads({','.join(cols)},status,created_at,updated_at) VALUES({','.join('?'*len(cols))},'new',?,?)",
                     (*vals, now(), now()))
        self.log(lid, "created", lead.get("source") or "")
        return lid, True

    def lead(self, lid: int):
        return self.one("SELECT * FROM leads WHERE id=?", (lid,))

    def update_lead(self, lid: int, **fields) -> None:
        if not fields:
            return
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError(f"unknown status {fields['status']!r}; one of {STATUSES}")
        sets = ", ".join(f"{k}=?" for k in fields)
        self.x(f"UPDATE leads SET {sets}, updated_at=? WHERE id=?", (*fields.values(), now(), lid))
        if "status" in fields:
            self.log(lid, "status", fields["status"])

    def leads(self, status: str | None = None, limit: int = 50, industry: str | None = None, city: str | None = None):
        sql, args = "SELECT * FROM leads WHERE 1=1", []
        if status:
            sql += " AND status IN (%s)" % ",".join("?" * len(status.split(",")))
            args += status.split(",")
        if industry:
            sql += " AND industry LIKE ?"
            args.append(f"%{industry}%")
        if city:
            sql += " AND city LIKE ?"
            args.append(f"%{city}%")
        sql += " ORDER BY COALESCE(score,-1) DESC, id LIMIT ?"
        args.append(limit)
        return self.q(sql, args)

    # ---- site data
    def save_site(self, lid: int, data: dict, text: str) -> None:
        self.x("INSERT INTO site_data(lead_id,data,text,analyzed_at) VALUES(?,?,?,?) "
               "ON CONFLICT(lead_id) DO UPDATE SET data=excluded.data, text=excluded.text, analyzed_at=excluded.analyzed_at",
               (lid, json.dumps(data), text, now()))

    def site(self, lid: int) -> tuple[dict, str]:
        r = self.one("SELECT data,text FROM site_data WHERE lead_id=?", (lid,))
        return (json.loads(r["data"]), r["text"]) if r else ({}, "")

    # ---- contacts
    def add_contact(self, lid: int, first="", last="", role="", email="", email_status="", email_source="", primary=True) -> int:
        if primary:
            self.x("UPDATE contacts SET is_primary=0 WHERE lead_id=?", (lid,))
        cid = self.x("INSERT INTO contacts(lead_id,first,last,role,email,email_status,email_source,is_primary,created_at) "
                     "VALUES(?,?,?,?,?,?,?,?,?)", (lid, first, last, role, (email or "").lower() or None,
                                                    email_status, email_source, 1 if primary else 0, now()))
        self.log(lid, "contact", f"{first} {last} <{email}> {role}".strip())
        return cid

    def primary_contact(self, lid: int):
        return self.one("SELECT * FROM contacts WHERE lead_id=? ORDER BY is_primary DESC, id DESC LIMIT 1", (lid,))

    def contacts(self, lid: int):
        return self.q("SELECT * FROM contacts WHERE lead_id=? ORDER BY is_primary DESC, id", (lid,))

    # ---- suppression
    def suppress(self, value: str, reason: str = "") -> None:
        self.x("INSERT OR IGNORE INTO suppression(value,reason,created_at) VALUES(?,?,?)", (value.lower().strip(), reason, now()))

    def is_suppressed(self, email: str) -> bool:
        e = (email or "").lower().strip()
        dom = "@" + e.split("@")[-1] if "@" in e else ""
        return bool(self.one("SELECT 1 FROM suppression WHERE value IN (?,?)", (e, dom)))

    # ---- messages
    def add_message(self, **m) -> int:
        m.setdefault("created_at", now())
        cols = list(m)
        return self.x(f"INSERT INTO messages({','.join(cols)}) VALUES({','.join('?'*len(cols))})", tuple(m.values()))

    def message(self, mid: int):
        return self.one("SELECT * FROM messages WHERE id=?", (mid,))

    def thread(self, lid: int):
        return self.q("SELECT * FROM messages WHERE lead_id=? ORDER BY COALESCE(sent_at,created_at), id", (lid,))

    def update_message(self, mid: int, **fields) -> None:
        sets = ", ".join(f"{k}=?" for k in fields)
        self.x(f"UPDATE messages SET {sets} WHERE id=?", (*fields.values(), mid))

    def sent_today(self, day_start_utc: str) -> int:
        return self.one("SELECT COUNT(*) c FROM messages WHERE direction='out' AND status='sent' AND sent_at>=?",
                        (day_start_utc,))["c"]

    def last_sent_at(self):
        r = self.one("SELECT MAX(sent_at) t FROM messages WHERE direction='out' AND status='sent'")
        return r["t"] if r else None


def open_db(cfg: dict) -> DB:
    from .config import data_dir
    return DB(data_dir(cfg) / "scout.db")
