"""Royalty-free media search: Pexels + Pixabay (both free for commercial use,
no attribution required). Get free API keys and export them:
  PEXELS_API_KEY  -> https://www.pexels.com/api/
  PIXABAY_API_KEY -> https://pixabay.com/api/docs/
"""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Studio/1.0"}


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def search(query: str, kind: str = "video", orientation: str = "landscape", n: int = 12) -> list[dict]:
    """Return [{source, preview, download, page, duration, width, height, credit}]."""
    if kind == "music":
        return music_links(query)
    results, errors = [], []
    for fn in (_pexels, _pixabay):
        try:
            results += fn(query, kind, orientation, n)
        except Exception as e:  # one source down shouldn't kill the search
            errors.append(f"{fn.__name__[1:]}: {e}")
    if not results and errors:
        raise RuntimeError("; ".join(errors))
    return results


def _pexels(q, kind, orientation, n):
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("PEXELS_API_KEY not set")
    qs = urllib.parse.urlencode({"query": q, "orientation": orientation, "per_page": n})
    if kind == "video":
        data = _get(f"https://api.pexels.com/videos/search?{qs}", {"Authorization": key})
        out = []
        for v in data.get("videos", []):
            files = [f for f in v["video_files"] if f.get("width") and f["file_type"] == "video/mp4"]
            if not files:
                continue
            # best file at or below 1920 wide
            f = max((f for f in files if f["width"] <= 1920), key=lambda f: f["width"], default=files[0])
            out.append(dict(source="pexels", preview=v["image"], download=f["link"], page=v["url"],
                            duration=v["duration"], width=f["width"], height=f["height"],
                            credit=v["user"]["name"]))
        return out
    data = _get(f"https://api.pexels.com/v1/search?{qs}", {"Authorization": key})
    return [dict(source="pexels", preview=p["src"]["medium"], download=p["src"]["large2x"], page=p["url"],
                 duration=0, width=p["width"], height=p["height"], credit=p["photographer"])
            for p in data.get("photos", [])]


def _pixabay(q, kind, orientation, n):
    key = os.getenv("PIXABAY_API_KEY")
    if not key:
        raise RuntimeError("PIXABAY_API_KEY not set")
    qs = urllib.parse.urlencode({"key": key, "q": q, "per_page": max(3, n), "safesearch": "true"})
    if kind == "video":
        data = _get(f"https://pixabay.com/api/videos/?{qs}")
        out = []
        for h in data.get("hits", []):
            v = h["videos"].get("large") or h["videos"]["medium"]
            if not v.get("url"):
                continue
            if (orientation == "portrait") != (v["height"] > v["width"]):
                continue
            out.append(dict(source="pixabay", preview=v.get("thumbnail", ""), download=v["url"],
                            page=h["pageURL"], duration=h["duration"], width=v["width"],
                            height=v["height"], credit=h["user"]))
        return out
    data = _get(f"https://pixabay.com/api/?{qs}&image_type=photo&orientation="
                f"{'vertical' if orientation == 'portrait' else 'horizontal'}")
    return [dict(source="pixabay", preview=h["webformatURL"], download=h["largeImageURL"], page=h["pageURL"],
                 duration=0, width=h["imageWidth"], height=h["imageHeight"], credit=h["user"])
            for h in data.get("hits", [])]


def music_links(q: str) -> list[dict]:
    """No free music API allows bulk download, so return search links to safe libraries."""
    enc = urllib.parse.quote(q)
    return [
        dict(source="Pixabay Music", page=f"https://pixabay.com/music/search/{enc}/",
             note="Free for commercial use, no attribution needed"),
        dict(source="YouTube Audio Library", page="https://studio.youtube.com/",
             note="Studio > Audio Library. Safest choice for monetised YouTube."),
        dict(source="Free Music Archive", page=f"https://freemusicarchive.org/search?quicksearch={enc}",
             note="Check each track's licence (CC BY is fine with credit)"),
    ]


def download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, dest.open("wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    return dest
