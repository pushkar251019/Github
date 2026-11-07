"""Find and download PDFs: scan any web page for PDF links, search free
public-domain libraries, download safely and extract text page by page."""
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse, quote

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .config import LIBRARY_DIR, MAX_PDF_BYTES, USER_AGENT
from . import library

HEADERS = {"User-Agent": USER_AGENT}


class FetchError(Exception):
    pass


def _check_public_url(url: str) -> None:
    """Block non-http(s) and private/loopback hosts (SSRF guard)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise FetchError("Only http(s) URLs are supported")
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except socket.gaierror as e:
        raise FetchError(f"Cannot resolve host {p.hostname}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise FetchError("Refusing to fetch private/internal addresses")


def _client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30)


def scan_page(url: str) -> list[dict]:
    """Return every PDF link on a web page (or the URL itself if it is a PDF)."""
    _check_public_url(url)
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "pdf" in ctype or r.content[:5] == b"%PDF-":
            return [{"title": _name_from_url(url), "url": str(r.url), "source": "direct"}]
        return extract_pdf_links(r.text, str(r.url))


def extract_pdf_links(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].strip())
        path = urlparse(href).path.lower()
        text = " ".join(a.get_text(" ").split())
        if path.endswith(".pdf") or "/pdf/" in path or "format=pdf" in href.lower() \
                or (text.lower().endswith("pdf") and len(text) < 40):
            if href in seen:
                continue
            seen.add(href)
            title = text if text and text.lower() not in ("pdf", "download", "download pdf") else _name_from_url(href)
            out.append({"title": title[:200], "url": href, "source": urlparse(base_url).netloc})
    return out


def _name_from_url(url: str) -> str:
    name = urlparse(url).path.rstrip("/").split("/")[-1] or "document"
    return re.sub(r"\.pdf$", "", name, flags=re.I).replace("_", " ").replace("-", " ") or "document"


def search_free_books(query: str, limit: int = 15) -> list[dict]:
    """Search Internet Archive (PDFs) and Project Gutenberg (public domain)."""
    results: list[dict] = []
    with _client() as c:
        try:
            r = c.get("https://archive.org/advancedsearch.php", params={
                "q": f'({query}) AND mediatype:texts AND format:PDF',
                "fl[]": ["identifier", "title", "creator", "year"],
                "rows": limit, "output": "json",
            })
            for d in r.json().get("response", {}).get("docs", []):
                ident = d["identifier"]
                creator = d.get("creator")
                if isinstance(creator, list):
                    creator = ", ".join(creator)
                results.append({
                    "title": d.get("title", ident), "author": creator or "",
                    "year": d.get("year", ""), "source": "Internet Archive",
                    "page": f"https://archive.org/details/{ident}",
                    "resolve": f"ia:{ident}",
                })
        except Exception:
            pass
        try:
            r = c.get("https://gutendex.com/books", params={"search": query})
            for b in r.json().get("results", [])[:limit]:
                fmts = b.get("formats", {})
                pdf = next((u for k, u in fmts.items() if "pdf" in k), None)
                txt = next((u for k, u in fmts.items() if k.startswith("text/plain")), None)
                if not (pdf or txt):
                    continue
                results.append({
                    "title": b.get("title", ""),
                    "author": ", ".join(a["name"] for a in b.get("authors", [])),
                    "year": "", "source": "Project Gutenberg",
                    "page": f"https://www.gutenberg.org/ebooks/{b['id']}",
                    "url": pdf or "", "text_url": "" if pdf else txt,
                })
        except Exception:
            pass
    return results


def resolve_ia(identifier: str) -> str:
    """Find the main PDF file of an Internet Archive item."""
    with _client() as c:
        meta = c.get(f"https://archive.org/metadata/{quote(identifier)}").json()
    pdfs = [f for f in meta.get("files", []) if f.get("name", "").lower().endswith(".pdf")]
    if not pdfs:
        raise FetchError("No PDF in this Internet Archive item")
    best = max(pdfs, key=lambda f: int(f.get("size", 0) or 0))
    return f"https://archive.org/download/{quote(identifier)}/{quote(best['name'])}"


def download_pdf(url: str, title: str = "") -> dict:
    if url.startswith("ia:"):
        url = resolve_ia(url[3:])
    _check_public_url(url)
    item = library.add_item("pdf", title or _name_from_url(url), source=url)
    dest = LIBRARY_DIR / f"{item['id']}.pdf"
    size = 0
    try:
        with _client() as c, c.stream("GET", url) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                first = True
                for chunk in r.iter_bytes(65536):
                    if first:
                        if not chunk.lstrip()[:5].startswith(b"%PDF"):
                            raise FetchError("That link did not return a PDF file")
                        first = False
                    size += len(chunk)
                    if size > MAX_PDF_BYTES:
                        raise FetchError("PDF is larger than the size limit")
                    f.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        library.delete_item(item["id"])
        raise
    pages = extract_pages(dest)
    text = "\f".join(pages)  # \f = page break, lets the UI pick page ranges
    library.update_item(item["id"], file=dest.name)
    library.set_text(item["id"], text)
    meta = {"pages": len(pages), "bytes": size, "chars": len(text)}
    return library.update_item(item["id"], meta=meta)


def download_text(url: str, title: str) -> dict:
    """For Gutenberg books that only have plain text."""
    _check_public_url(url)
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
    text = strip_gutenberg_boilerplate(r.text)
    return library.add_item("book", title, text=text, source=url, meta={"chars": len(text)})


def strip_gutenberg_boilerplate(text: str) -> str:
    start = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", text, re.I)
    end = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", text, re.I)
    return text[start.end() if start else 0: end.start() if end else len(text)].strip()


def extract_pages(path) -> list[str]:
    reader = PdfReader(str(path))
    pages = []
    for p in reader.pages:
        try:
            pages.append(clean_text(p.extract_text() or ""))
        except Exception:
            pages.append("")
    return pages


def clean_text(t: str) -> str:
    t = re.sub(r"-\n(\w)", r"\1", t)            # re-join hyphenated words
    t = re.sub(r"(?<![.!?:\"'”])\n(?!\n)", " ", t)  # unwrap soft line breaks
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()
