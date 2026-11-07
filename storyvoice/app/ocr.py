"""Get readable text out of scanned PDFs (page images with no text layer).

1. Internet Archive books: IA already OCRs every scan and publishes the text
   (`*_djvu.txt`), so we just fetch it — fast, no extra software.
2. Any other scanned PDF: render pages with pypdfium2 and OCR them with
   Tesseract (optional install; supports Hindi with the `hin` language pack).
"""
import re
import shutil
from urllib.parse import quote, unquote, urlparse

from . import library, pdf_finder

MIN_WORDS_PER_PAGE = 5


def needs_ocr(text: str) -> bool:
    pages = text.split("\f") if text else [""]
    words = len(text.split())
    return words < max(30, MIN_WORDS_PER_PAGE * len(pages) * 0.2)


def ia_identifier(url: str) -> str | None:
    p = urlparse(url or "")
    if not p.hostname or not p.hostname.endswith("archive.org"):
        return None
    m = re.match(r"/(?:download|details)/([^/]+)", p.path)
    return unquote(m.group(1)) if m else None


def split_pseudo_pages(text: str, size: int = 1800) -> list[str]:
    """IA text has no reliable page marks; cut it into ~page-sized chunks at
    paragraph boundaries so the page-range picker still works."""
    if "\f" in text:
        return [p.strip() for p in text.split("\f")]
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pages, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > size:
            pages.append(cur)
            cur = ""
        cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        pages.append(cur)
    return pages or [""]


def fetch_ia_text(identifier: str) -> str:
    with pdf_finder._client() as c:
        meta = c.get(f"https://archive.org/metadata/{quote(identifier)}").json()
        txts = [f["name"] for f in meta.get("files", []) if f.get("name", "").endswith("_djvu.txt")]
        if not txts:
            return ""
        r = c.get(f"https://archive.org/download/{quote(identifier)}/{quote(txts[0])}")
        r.raise_for_status()
        return r.text


def tesseract_ocr(pdf_path, lang: str = "eng+hin", first: int = 1, last: int = 0,
                  progress=lambda m, f=None: None) -> list[str]:
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError as e:
        raise RuntimeError("OCR needs: pip install pypdfium2 pytesseract") from e
    if not shutil.which("tesseract"):
        for guess in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                      r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
            if shutil.os.path.exists(guess):
                pytesseract.pytesseract.tesseract_cmd = guess
                break
        else:
            raise RuntimeError("This is a scanned PDF. To read it, install Tesseract OCR "
                               "(Windows: winget install UB-Mannheim.TesseractOCR, and tick "
                               "Hindi in the installer) then try again.")
    available = set(pytesseract.get_languages(config=""))
    langs = "+".join(l for l in lang.split("+") if l in available) or "eng"
    pdf = pdfium.PdfDocument(str(pdf_path))
    last = min(last or len(pdf), len(pdf))
    out = []
    for i in range(first - 1, last):
        progress(f"Reading scanned page {i + 1}/{last}…", (i - first + 1) / max(1, last - first + 1))
        img = pdf[i].render(scale=2.5).to_pil()
        out.append(pdf_finder.clean_text(pytesseract.image_to_string(img, lang=langs)))
    return out


def ocr_item(item_id: str, first: int = 1, last: int = 0, progress=lambda m, f=None: None) -> dict:
    item = library.get_item(item_id)
    if not item:
        raise KeyError(item_id)
    ident = ia_identifier(item.get("source", ""))
    if ident:
        progress("Fetching Internet Archive's text for this scan…")
        text = fetch_ia_text(ident)
        if len(text.split()) > 50:
            pages = split_pseudo_pages(text)
            library.set_text(item_id, "\f".join(pages))
            meta = {**item.get("meta", {}), "pages": len(pages), "text_source": "archive.org OCR"}
            return library.update_item(item_id, meta=meta)
    path = library.file_path(item)
    if not path or not path.exists():
        raise RuntimeError("No PDF file to read")
    pages = tesseract_ocr(path, first=first, last=last, progress=progress)
    old = library.get_text(item_id).split("\f")
    if len(old) < first - 1 + len(pages):
        old += [""] * (first - 1 + len(pages) - len(old))
    old[first - 1: first - 1 + len(pages)] = pages
    library.set_text(item_id, "\f".join(old))
    meta = {**item.get("meta", {}), "text_source": "tesseract OCR"}
    return library.update_item(item_id, meta=meta)
