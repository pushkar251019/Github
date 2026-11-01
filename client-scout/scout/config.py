"""Workspace + config loading. Config lives in scout.json at the workspace root."""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS: dict = {
    "business": {},
    "sender": {
        "name": "",
        "email": "",
        "company": "",
        "signature": "",
        "physical_address": "",
        "booking_link": "",
    },
    "smtp": {"host": "smtp.gmail.com", "port": 587, "user": "", "password_env": "SCOUT_EMAIL_PASSWORD", "ssl": False},
    "imap": {"host": "imap.gmail.com", "port": 993, "user": "", "password_env": "SCOUT_EMAIL_PASSWORD", "folder": "INBOX"},
    "sending": {
        "mode": "review",          # review = human approves each draft; auto = agent sends approved-by-rules drafts
        "daily_limit": 30,
        "min_gap_seconds": 90,
        "jitter_seconds": 60,
        "window_hours": [9, 17],
        "weekdays_only": True,
        "timezone": "",            # IANA name, e.g. "America/New_York"; empty = machine local time
        "opt_out_line": "Not relevant? Reply \"no thanks\" and I won't email again.",
    },
    "sequence": {"followup_days": [3, 7, 14], "max_followups": 3},
    "discovery": {"user_agent": "", "country": "US", "respect_robots": True, "request_delay": 1.0},
    "verify": {"smtp_probe": True, "helo_host": "", "mail_from": "", "timeout": 10},
}


def find_home(start: Path | None = None) -> Path:
    env = os.environ.get("SCOUT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    p = (start or Path.cwd()).resolve()
    for d in [p, *p.parents]:
        if (d / "scout.json").exists():
            return d
    return p


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(home: Path | None = None) -> dict:
    home = home or find_home()
    path = home / "scout.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    cfg = _merge(DEFAULTS, data)
    cfg["_home"] = str(home)
    cfg["_path"] = str(path)
    return cfg


def save(cfg: dict) -> None:
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    Path(cfg["_path"]).write_text(json.dumps(clean, indent=2) + "\n")


def data_dir(cfg: dict) -> Path:
    d = Path(cfg["_home"]) / ".scout"
    d.mkdir(parents=True, exist_ok=True)
    return d


def secret(section: dict) -> str:
    env = section.get("password_env") or "SCOUT_EMAIL_PASSWORD"
    return os.environ.get(env, "")


def user_agent(cfg: dict) -> str:
    ua = cfg["discovery"].get("user_agent")
    if ua:
        return ua
    contact = cfg["sender"].get("email") or "unknown"
    return f"ClientScout/0.1 (B2B research; contact {contact})"
