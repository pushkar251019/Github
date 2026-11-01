"""Website intelligence: contact details, people, marketing/ad signals, tech stack, site health."""
from __future__ import annotations

import html as htmllib
import json
import re
import urllib.parse
from datetime import date
from html.parser import HTMLParser

from . import net

PAGE_HINTS = ["about", "team", "staff", "our-story", "who-we-are", "meet", "doctor", "dentist", "attorney",
              "founder", "leadership", "people", "contact", "owner", "bio", "practitioner", "providers"]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
OBFUSCATED_RE = re.compile(r"([A-Za-z0-9._%+-]+)\s*[\[\(\{]\s*at\s*[\]\)\}]\s*([A-Za-z0-9.-]+)\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*([A-Za-z]{2,})", re.I)
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
JUNK_EMAIL = re.compile(r"(sentry|wixpress|example\.|domain\.com|email\.com|yourdomain|\.png|\.jpg|\.jpeg|\.gif|\.webp|"
                        r"\.svg|@2x|godaddy|squarespace|schema\.org|u003e|noreply|no-reply)", re.I)

SIGNALS = {
    # paid ads / tracking -> they spend on marketing (budget signal)
    "meta_pixel": [r"connect\.facebook\.net/[^\"']*/fbevents\.js", r"fbq\(\s*['\"]init"],
    "google_ads": [r"googleadservices\.com", r"['\"]AW-\d{6,}", r"google_conversion_id", r"gtag\/js\?id=AW-"],
    "google_analytics": [r"gtag\/js\?id=G-", r"google-analytics\.com/(analytics|ga)\.js", r"['\"]G-[A-Z0-9]{6,}['\"]"],
    "google_tag_manager": [r"googletagmanager\.com/gtm\.js", r"GTM-[A-Z0-9]{4,}"],
    "tiktok_pixel": [r"analytics\.tiktok\.com", r"ttq\.load"],
    "linkedin_insight": [r"snap\.licdn\.com", r"_linkedin_partner_id"],
    "hotjar": [r"static\.hotjar\.com"],
    "microsoft_ads": [r"bat\.bing\.com"],
    # site builders
    "wordpress": [r"wp-content/", r"wp-includes/"],
    "wix": [r"static\.wixstatic\.com", r"wix\.com"],
    "squarespace": [r"squarespace\.com", r"static1\.squarespace"],
    "shopify": [r"cdn\.shopify\.com", r"myshopify\.com"],
    "webflow": [r"webflow\.(com|io)", r"data-wf-site"],
    "godaddy_builder": [r"img1\.wsimg\.com", r"godaddy"],
    "duda": [r"dudaone|multiscreensite"],
    # conversion tooling
    "online_booking": [r"calendly\.com", r"acuityscheduling", r"zocdoc", r"opentable", r"mindbody", r"vagaro",
                       r"booksy", r"squareup\.com/appointments", r"setmore", r"simplybook", r"fresha", r"nexhealth",
                       r"localmed", r"resy\.com", r"housecallpro", r"jobber", r"servicetitan"],
    "live_chat": [r"intercom", r"drift\.com", r"tawk\.to", r"tidio", r"crisp\.chat", r"livechatinc", r"podium",
                  r"birdeye", r"zendesk"],
    "reviews_widget": [r"birdeye", r"podium", r"elfsight", r"trustpilot", r"yotpo", r"reviews\.io"],
    "email_capture": [r"mailchimp", r"klaviyo", r"convertkit", r"hubspot", r"activecampaign", r"constantcontact"],
    "ecommerce": [r"add[-_ ]to[-_ ]cart", r"woocommerce", r"/cart\b"],
}

SOCIAL_RE = {
    "facebook": r"https?://(?:www\.)?facebook\.com/(?!sharer|plugins|tr\?|dialog)[A-Za-z0-9_.\-/]+",
    "instagram": r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+",
    "linkedin": r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|in)/[A-Za-z0-9_\-%]+",
    "youtube": r"https?://(?:www\.)?youtube\.com/(?:@|c/|channel/|user/)[A-Za-z0-9_\-]+",
    "tiktok": r"https?://(?:www\.)?tiktok\.com/@[A-Za-z0-9_.]+",
    "x": r"https?://(?:www\.)?(?:twitter|x)\.com/(?!share|intent)[A-Za-z0-9_]+",
}

ROLE_WORDS = r"(owner|founder|co-founder|ceo|president|principal|managing (?:partner|director)|director|partner|" \
             r"proprietor|head chef|chef|general manager|practice manager|office manager|dds|dmd|md|esq\.?|cpa)"
NAME = r"(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z]\.)?\s+(?:[A-Z][a-z]+(?:-[A-Z][a-z]+)?|Mc[A-Z][a-z]+|O'[A-Z][a-z]+))"
PEOPLE_PATTERNS = [
    re.compile(NAME + r"\s*[,\-–|]\s*(?:the\s+)?" + ROLE_WORDS),
    re.compile(ROLE_WORDS + r"[\s:,\-–]+(?:Dr\.?\s+)?" + NAME[len(r"(?:Dr\.?\s+)?"):]),
    re.compile(r"(?:founded|owned|started|run)\s+(?:in\s+\d{4}\s+)?by\s+" + NAME),
    re.compile(r"(?:Meet|Hi,? I'?m|My name is)\s+" + NAME),
    re.compile(r"\bDr\.\s+([A-Z][a-z]+\s+[A-Z][a-z]+)"),
]
NOT_NAMES = {"Privacy Policy", "Contact Us", "Read More", "Learn More", "Book Now", "Our Team", "Family Dentistry",
             "Cosmetic Dentistry", "General Manager", "Terms Of", "All Rights", "Google Maps", "Real Estate"}


class _Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._skip = 0
        self._a: str | None = None
        self._atext: list[str] = []
        self.title = ""
        self._in_title = False
        self.meta: dict[str, str] = {}
        self.jsonld: list[str] = []
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
            if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
                self._in_jsonld = True
        elif tag == "a" and a.get("href"):
            self._a, self._atext = a["href"], []
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            k = (a.get("name") or a.get("property") or "").lower()
            if k:
                self.meta[k] = a.get("content") or ""
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "section", "tr", "footer", "header"):
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip = max(0, self._skip - 1)
            self._in_jsonld = False
        elif tag == "a" and self._a is not None:
            self.links.append((self._a, " ".join(self._atext).strip()))
            self._a = None
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_jsonld:
            self.jsonld.append(data)
            return
        if self._skip:
            return
        if self._in_title:
            self.title += data
        self.text.append(data)
        if self._a is not None:
            self._atext.append(data.strip())


def parse_html(raw: str) -> _Extract:
    p = _Extract()
    try:
        p.feed(raw)
    except Exception:
        pass
    return p


def clean_text(parts: list[str]) -> str:
    t = htmllib.unescape("".join(parts))
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def extract_emails(raw: str, text: str, domain: str = "") -> list[str]:
    found = set()
    for m in re.findall(r"mailto:([^\"'?>\s]+)", raw, re.I):
        found.add(urllib.parse.unquote(m))
    found.update(EMAIL_RE.findall(text))
    found.update(EMAIL_RE.findall(raw))
    for u, d, tld in OBFUSCATED_RE.findall(text):
        found.add(f"{u}@{d}.{tld}")
    emails = []
    for e in found:
        e = e.strip(".,;:").lower()
        if not EMAIL_RE.fullmatch(e) or JUNK_EMAIL.search(e) or len(e) > 80:
            continue
        emails.append(e)
    # same-domain first
    return sorted(set(emails), key=lambda e: (not (domain and e.endswith("@" + domain) or e.endswith("." + domain)), e))


def detect_signals(raw: str) -> list[str]:
    return [k for k, pats in SIGNALS.items() if any(re.search(p, raw, re.I) for p in pats)]


def extract_socials(raw: str) -> dict[str, str]:
    out = {}
    for k, pat in SOCIAL_RE.items():
        m = re.search(pat, raw)
        if m:
            out[k] = m.group(0).rstrip("/\"'")
    return out


def extract_people(text: str, jsonld: list[str]) -> list[dict]:
    people: dict[str, dict] = {}

    def add(name: str, role: str, src: str):
        name = re.sub(r"\s+", " ", name).strip()
        if name in NOT_NAMES or len(name.split()) < 2 or len(name) > 40:
            return
        cur = people.setdefault(name, {"name": name, "role": role, "source": src, "mentions": 0})
        cur["mentions"] += 1
        if role and not cur["role"]:
            cur["role"] = role

    for blob in jsonld:
        try:
            data = json.loads(blob)
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                for key in ("founder", "employee", "author", "member", "owner"):
                    v = d.get(key)
                    for p in (v if isinstance(v, list) else [v]):
                        if isinstance(p, dict) and p.get("name"):
                            add(p["name"], p.get("jobTitle") or key, "json-ld")
                if d.get("@type") == "Person" and d.get("name"):
                    add(d["name"], d.get("jobTitle", ""), "json-ld")
                stack.extend(v for v in d.values() if isinstance(v, (dict, list)))
            elif isinstance(d, list):
                stack.extend(d)

    for line in text.splitlines():
        if len(line) > 400:
            line = line[:400]
        for i, pat in enumerate(PEOPLE_PATTERNS):
            for m in pat.finditer(line):
                groups = [g for g in m.groups() if g]
                if not groups:
                    continue
                name = next((g for g in groups if re.match(r"[A-Z][a-z]+ ", g)), None)
                role = next((g for g in groups if re.fullmatch(ROLE_WORDS, g, re.I)), "")
                if name:
                    add(name, role.lower(), "text")
    ranked = sorted(people.values(), key=lambda p: (-(p["source"] == "json-ld"), -bool(p["role"]), -p["mentions"]))
    return ranked[:8]


def site_health(raw: str, text: str, meta: dict, final_url: str, elapsed: float) -> dict:
    years = [int(y) for y in re.findall(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(\d{4})", raw, re.I)]
    year = max(years) if years else None
    return {
        "https": final_url.startswith("https://"),
        "mobile_viewport": "viewport" in meta,
        "meta_description": bool(meta.get("description")),
        "copyright_year": year,
        "stale_copyright": bool(year and year < date.today().year - 1),
        "load_seconds": round(elapsed, 2),
        "word_count": len(text.split()),
        "has_blog": bool(re.search(r"/blog|/news|/articles", raw, re.I)),
        "has_testimonials": bool(re.search(r"testimonial|reviews?|what (?:our )?(?:clients|patients|customers) say", text, re.I)),
        "has_pricing": bool(re.search(r"\bpricing\b|\bprices\b|\$\d", text, re.I)),
        "has_cta_form": bool(re.search(r"<form", raw, re.I)),
    }


def candidate_pages(base_url: str, links: list[tuple[str, str]], limit: int = 4) -> list[str]:
    base_dom = net.domain_of(base_url)
    scored = []
    for href, label in links:
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        url = urllib.parse.urljoin(base_url, href).split("#")[0]
        if net.domain_of(url) != base_dom or re.search(r"\.(pdf|jpg|png|zip|docx?)$", url, re.I):
            continue
        hay = (urllib.parse.urlsplit(url).path + " " + label).lower()
        score = sum(2 if h in hay else 0 for h in PAGE_HINTS[:8]) + sum(1 for h in PAGE_HINTS[8:] if h in hay)
        if score:
            scored.append((score, url))
    out, seen = [], {base_url.rstrip("/")}
    for _, u in sorted(scored, key=lambda x: -x[0]):
        if u.rstrip("/") not in seen:
            seen.add(u.rstrip("/"))
            out.append(u)
        if len(out) >= limit:
            break
    return out


def ad_library_links(name: str, domain: str, country: str = "US") -> dict:
    q = urllib.parse.quote(name)
    return {
        "meta_ad_library": f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={country}"
                           f"&q={q}&search_type=keyword_unordered&media_type=all",
        "google_ads_transparency": f"https://adstransparency.google.com/?region={country}&domain={domain}" if domain
                                   else f"https://adstransparency.google.com/?region={country}",
        "linkedin_ads": f"https://www.linkedin.com/ad-library/search?accountOwner={q}",
    }


def analyze(url: str, ua: str, name: str = "", country: str = "US", max_pages: int = 4,
            respect_robots: bool = True, delay: float = 1.0) -> tuple[dict, str]:
    url = net.normalize_url(url)
    home = net.fetch(url, ua, delay=delay, check_robots=respect_robots)
    if not home.ok and url.startswith("https://"):
        home = net.fetch("http://" + url[8:], ua, delay=delay, check_robots=respect_robots)
    if not home.ok:
        return {"reachable": False, "status": home.status, "url": url,
                "ads": ad_library_links(name, net.domain_of(url), country)}, ""
    domain = net.domain_of(home.final_url)
    p = parse_html(home.text)
    raw_all, texts, jsonld, pages = home.text, [f"[PAGE] {home.final_url}\n" + clean_text(p.text)], list(p.jsonld), [home.final_url]
    for sub in candidate_pages(home.final_url, p.links, max_pages):
        r = net.fetch(sub, ua, delay=delay, check_robots=respect_robots)
        if r.ok:
            sp = parse_html(r.text)
            raw_all += "\n" + r.text
            texts.append(f"[PAGE] {r.final_url}\n" + clean_text(sp.text))
            jsonld += sp.jsonld
            pages.append(r.final_url)
    text = "\n\n".join(texts)
    data = {
        "reachable": True,
        "url": home.final_url,
        "domain": domain,
        "title": p.title.strip()[:200],
        "description": (p.meta.get("description") or p.meta.get("og:description") or "")[:300],
        "pages": pages,
        "emails": extract_emails(raw_all, text, domain)[:10],
        "phones": sorted(set(m.strip() for m in PHONE_RE.findall(text)))[:5],
        "socials": extract_socials(raw_all),
        "signals": detect_signals(raw_all),
        "people": extract_people(text, jsonld),
        "health": site_health(home.text, clean_text(p.text), p.meta, home.final_url, home.elapsed),
        "ads": ad_library_links(name or p.title, domain, country),
    }
    data["running_ads_likely"] = any(s in data["signals"] for s in ("meta_pixel", "google_ads", "tiktok_pixel",
                                                                    "microsoft_ads", "linkedin_insight"))
    return data, text[:20000]
