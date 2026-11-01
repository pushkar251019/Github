"""Business discovery from free, open data: OpenStreetMap (Nominatim + Overpass).

No API key, no scraping of Google Maps (which breaks its ToS). For better
coverage the agent can also add businesses it finds via web search
(`scout add`) or import any CSV you already have (`scout import`).
"""
from __future__ import annotations

import csv
import json
import re
import urllib.parse

from . import net

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Plain-English industry -> OSM tag filters. Use `--tag key=value` for anything else.
INDUSTRY_TAGS: dict[str, list[str]] = {
    "dentist": ["amenity=dentist", "healthcare=dentist"],
    "doctor": ["amenity=doctors", "healthcare=doctor"],
    "clinic": ["amenity=clinic", "healthcare=clinic"],
    "chiropractor": ["healthcare=chiropractor"],
    "physiotherapist": ["healthcare=physiotherapist"],
    "optician": ["shop=optician", "healthcare=optometrist"],
    "pharmacy": ["amenity=pharmacy"],
    "veterinary": ["amenity=veterinary"],
    "med spa": ["shop=beauty", "amenity=spa", "leisure=spa"],
    "spa": ["amenity=spa", "leisure=spa"],
    "salon": ["shop=hairdresser", "shop=beauty"],
    "barber": ["shop=hairdresser"],
    "beauty": ["shop=beauty", "shop=cosmetics"],
    "tattoo": ["shop=tattoo"],
    "gym": ["leisure=fitness_centre", "leisure=sports_centre"],
    "yoga": ["sport=yoga", "leisure=fitness_centre"],
    "restaurant": ["amenity=restaurant"],
    "cafe": ["amenity=cafe"],
    "bar": ["amenity=bar", "amenity=pub"],
    "bakery": ["shop=bakery"],
    "hotel": ["tourism=hotel", "tourism=guest_house"],
    "lawyer": ["office=lawyer"],
    "accountant": ["office=accountant", "office=tax_advisor"],
    "financial advisor": ["office=financial_advisor", "office=financial"],
    "insurance": ["office=insurance"],
    "real estate": ["office=estate_agent"],
    "architect": ["office=architect"],
    "marketing agency": ["office=advertising_agency", "office=marketing"],
    "it services": ["office=it", "office=company"],
    "consulting": ["office=consulting"],
    "coworking": ["amenity=coworking_space", "office=coworking"],
    "plumber": ["craft=plumber"],
    "electrician": ["craft=electrician"],
    "hvac": ["craft=hvac"],
    "roofer": ["craft=roofer"],
    "builder": ["craft=builder", "office=construction_company"],
    "carpenter": ["craft=carpenter"],
    "painter": ["craft=painter"],
    "landscaper": ["craft=gardener", "craft=landscaper"],
    "cleaning": ["office=cleaning", "craft=cleaning"],
    "locksmith": ["craft=locksmith", "shop=locksmith"],
    "photographer": ["craft=photographer", "shop=photo"],
    "auto repair": ["shop=car_repair"],
    "car dealer": ["shop=car"],
    "car wash": ["amenity=car_wash"],
    "driving school": ["amenity=driving_school"],
    "school": ["amenity=school", "amenity=college"],
    "tutoring": ["amenity=prep_school", "office=educational_institution"],
    "kindergarten": ["amenity=kindergarten", "amenity=childcare"],
    "furniture": ["shop=furniture"],
    "jewelry": ["shop=jewelry"],
    "clothing": ["shop=clothes", "shop=boutique"],
    "florist": ["shop=florist"],
    "pet": ["shop=pet", "amenity=animal_boarding", "shop=pet_grooming"],
    "event venue": ["amenity=events_venue", "amenity=conference_centre"],
    "travel agency": ["shop=travel_agency", "office=travel_agent"],
    "printing": ["shop=copyshop", "craft=printer"],
}


def resolve_tags(industry: str | None, tags: list[str] | None) -> list[str]:
    out = list(tags or [])
    if industry:
        key = industry.lower().strip()
        if key in INDUSTRY_TAGS:
            out += INDUSTRY_TAGS[key]
        else:
            for k, v in INDUSTRY_TAGS.items():
                if key.rstrip("s") in k or k in key:
                    out += v
    seen, uniq = set(), []
    for t in out:
        if t not in seen and re.match(r"^[a-z_:]+=[A-Za-z0-9_ :;-]+$", t):
            seen.add(t)
            uniq.append(t)
    return uniq


def geocode(city: str, ua: str) -> dict:
    url = NOMINATIM + "?" + urllib.parse.urlencode({"q": city, "format": "json", "limit": 1})
    res = net.get_json(url, ua, delay=1.1)
    if not res:
        raise RuntimeError(f"Could not geocode {city!r}")
    r = res[0]
    return {"lat": float(r["lat"]), "lon": float(r["lon"]), "display": r.get("display_name", city)}


def build_query(tags: list[str], lat: float, lon: float, radius_m: int, name_regex: str | None = None,
                require_website: bool = False) -> str:
    parts = []
    for t in tags:
        k, v = t.split("=", 1)
        flt = f'["{k}"="{v}"]'
        if name_regex:
            flt += f'["name"~"{name_regex}",i]'
        if require_website:
            flt += '[~"^(website|contact:website|url)$"~"."]'
        parts.append(f"  nwr{flt}(around:{radius_m},{lat},{lon});")
    return "[out:json][timeout:60];\n(\n" + "\n".join(parts) + "\n);\nout center tags;"


def run_overpass(query: str, ua: str) -> list[dict]:
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for url in OVERPASS_MIRRORS:
        try:
            return net.get_json(url, ua, delay=1.0, data=data, timeout=90).get("elements", [])
        except Exception as e:  # try next mirror
            last = e
    raise RuntimeError(f"All Overpass mirrors failed: {last}")


def element_to_lead(el: dict, industry: str, city: str) -> dict | None:
    t = el.get("tags", {})
    name = t.get("name") or t.get("brand")
    if not name:
        return None
    website = t.get("website") or t.get("contact:website") or t.get("url") or ""
    website = net.normalize_url(website.split(";")[0])
    addr = " ".join(x for x in [t.get("addr:housenumber"), t.get("addr:street"), t.get("addr:city"),
                                 t.get("addr:postcode")] if x)
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    return {
        "name": name.strip(),
        "website": website,
        "domain": net.domain_of(website) if website else None,
        "phone": t.get("phone") or t.get("contact:phone"),
        "email": (t.get("email") or t.get("contact:email") or "").lower() or None,
        "address": addr or None,
        "city": t.get("addr:city") or city,
        "industry": industry,
        "lat": lat, "lon": lon,
        "source": "osm",
        "source_ref": f"osm:{el.get('type')}/{el.get('id')}",
        "notes": json.dumps({k: t[k] for k in ("opening_hours", "brand", "operator", "facebook", "contact:facebook",
                                                "instagram", "contact:instagram") if k in t}) or None,
    }


# Chains rarely buy from small vendors; skip by default.
CHAIN_HINTS = re.compile(r"\b(mcdonald|starbucks|subway|walmart|cvs|walgreens|aspen dental|heartland|"
                         r"planet fitness|anytime fitness|great clips|supercuts|jiffy lube|h&r block|"
                         r"state farm|allstate|re/max|keller williams|coldwell banker|century 21)\b", re.I)


def search(industry: str, city: str, ua: str, radius_km: float = 10, tags: list[str] | None = None,
           name_regex: str | None = None, require_website: bool = True, skip_chains: bool = True) -> list[dict]:
    tag_list = resolve_tags(industry, tags)
    if not tag_list:
        raise ValueError(f"No OSM tags for industry {industry!r}. Pass --tag key=value "
                         f"(see https://wiki.openstreetmap.org/wiki/Map_features) or one of: {', '.join(INDUSTRY_TAGS)}")
    geo = geocode(city, ua)
    q = build_query(tag_list, geo["lat"], geo["lon"], int(radius_km * 1000), name_regex, require_website)
    leads = []
    for el in run_overpass(q, ua):
        lead = element_to_lead(el, industry, city)
        if not lead:
            continue
        if skip_chains and (CHAIN_HINTS.search(lead["name"]) or "brand:wikidata" in el.get("tags", {})):
            continue
        leads.append(lead)
    return leads


def read_csv(path: str, industry: str = "", city: str = "") -> list[dict]:
    """Import any CSV with columns like name/company, website/url, phone, email, address, city, industry."""
    alias = {"company": "name", "business": "name", "business name": "name", "title": "name",
             "url": "website", "site": "website", "web": "website", "domain": "website",
             "telephone": "phone", "phone number": "phone", "e-mail": "email", "location": "address",
             "category": "industry", "type": "industry"}
    out = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            r = {}
            for k, v in row.items():
                if k is None:
                    continue
                kk = alias.get(k.strip().lower(), k.strip().lower())
                if v and kk not in r:
                    r[kk] = v.strip()
            if not r.get("name"):
                continue
            site = net.normalize_url(r.get("website", ""))
            out.append({
                "name": r["name"], "website": site, "domain": net.domain_of(site) if site else None,
                "phone": r.get("phone"), "email": (r.get("email") or "").lower() or None,
                "address": r.get("address"), "city": r.get("city") or city,
                "industry": r.get("industry") or industry, "source": "csv",
                "source_ref": None, "notes": None,
            })
    return out
