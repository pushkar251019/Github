"""Polite HTTP + DNS helpers (stdlib only)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
MAX_BYTES = 1_500_000


class FetchResult:
    def __init__(self, url: str, status: int, text: str, elapsed: float, final_url: str):
        self.url, self.status, self.text, self.elapsed, self.final_url = url, status, text, elapsed, final_url

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400 and bool(self.text)


def _throttle(host: str, delay: float) -> None:
    wait = _last_hit.get(host, 0) + delay - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.time()


def robots_allowed(url: str, ua: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=8) as r:
                rp.parse(r.read(200_000).decode("utf-8", "replace").splitlines())
            _robots[base] = rp
        except Exception:
            _robots[base] = None  # unreachable robots.txt = no restrictions
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(ua, url)


def fetch(url: str, ua: str, timeout: float = 15, delay: float = 1.0, check_robots: bool = True,
          data: bytes | None = None, headers: dict | None = None) -> FetchResult:
    host = urllib.parse.urlsplit(url).netloc
    if check_robots and data is None and not robots_allowed(url, ua):
        return FetchResult(url, 999, "", 0, url)  # 999 = blocked by robots.txt
    _throttle(host, delay)
    h = {"User-Agent": ua, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8", "Accept-Language": "en"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(MAX_BYTES)
            charset = r.headers.get_content_charset() or "utf-8"
            return FetchResult(url, r.status, raw.decode(charset, "replace"), time.time() - t0, r.geturl())
    except urllib.error.HTTPError as e:
        return FetchResult(url, e.code, "", time.time() - t0, url)
    except Exception:
        return FetchResult(url, 0, "", time.time() - t0, url)


def get_json(url: str, ua: str, delay: float = 1.0, data: bytes | None = None, timeout: float = 60):
    r = fetch(url, ua, timeout=timeout, delay=delay, check_robots=False, data=data)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status} from {url}")
    return json.loads(r.text)


def mx_records(domain: str, ua: str = "ClientScout") -> list[str]:
    """MX hosts sorted by priority. Tries DNS-over-HTTPS, then dig/nslookup."""
    for endpoint in ("https://dns.google/resolve", "https://cloudflare-dns.com/dns-query"):
        try:
            url = f"{endpoint}?name={urllib.parse.quote(domain)}&type=MX"
            r = fetch(url, ua, timeout=8, delay=0, check_robots=False, headers={"Accept": "application/dns-json"})
            if r.ok:
                ans = json.loads(r.text).get("Answer", []) or []
                recs = []
                for a in ans:
                    if a.get("type") == 15:
                        pr, host = a["data"].split(None, 1)
                        recs.append((int(pr), host.rstrip(".")))
                return [h for _, h in sorted(recs)]
        except Exception:
            continue
    if shutil.which("dig"):
        out = subprocess.run(["dig", "+short", "MX", domain], capture_output=True, text=True, timeout=10).stdout
        recs = [(int(p), h.rstrip(".")) for p, h in (l.split() for l in out.splitlines() if len(l.split()) == 2)]
        return [h for _, h in sorted(recs)]
    if shutil.which("nslookup"):
        out = subprocess.run(["nslookup", "-type=mx", domain], capture_output=True, text=True, timeout=10).stdout
        recs = [(int(p), h.rstrip(".")) for p, h in re.findall(r"preference\s*=\s*(\d+),\s*mail exchanger\s*=\s*(\S+)", out)]
        return [h for _, h in sorted(recs)]
    return []


def domain_of(url_or_email: str) -> str:
    s = (url_or_email or "").strip().lower()
    if "@" in s and "/" not in s:
        return s.split("@", 1)[1]
    if not re.match(r"^[a-z]+://", s):
        s = "http://" + s
    host = urllib.parse.urlsplit(s).hostname or ""
    return host[4:] if host.startswith("www.") else host


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url
