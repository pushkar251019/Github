"""StoryVoice API + web UI.  Run:  uvicorn app.main:app --port 8000"""
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import library, mood, music, narrate, ocr, pdf_finder, transcribe, tts
from .config import AUDIO_DIR, BASE_DIR, TMP_DIR

app = FastAPI(title="StoryVoice")
JOBS: dict[str, dict] = {}


def _run_job(kind: str, fn) -> str:
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"id": job_id, "kind": kind, "status": "running", "message": "Starting…",
                    "progress": 0.0, "result": None, "error": None}

    def progress(msg, frac=None):
        JOBS[job_id]["message"] = msg
        if frac is not None:
            JOBS[job_id]["progress"] = round(frac, 3)

    def work():
        try:
            JOBS[job_id]["result"] = fn(job_id, progress)
            JOBS[job_id].update(status="done", progress=1.0, message="Done")
        except Exception as e:  # surface the reason to the UI
            JOBS[job_id].update(status="error", error=str(e) or e.__class__.__name__)

    threading.Thread(target=work, daemon=True).start()
    return job_id


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Unknown job")
    return JOBS[job_id]


# ---------- PDFs ----------
@app.get("/api/pdf/scan")
def pdf_scan(url: str):
    try:
        return {"results": pdf_finder.scan_page(url)}
    except Exception as e:
        raise HTTPException(400, f"Could not scan page: {e}")


@app.get("/api/pdf/search")
def pdf_search(q: str):
    return {"results": pdf_finder.search_free_books(q)}


class DownloadReq(BaseModel):
    url: str = ""
    text_url: str = ""
    title: str = ""


@app.post("/api/pdf/download")
def pdf_download(req: DownloadReq):
    try:
        if req.text_url and not req.url:
            return pdf_finder.download_text(req.text_url, req.title or "Book")
        item = pdf_finder.download_pdf(req.url, req.title)
    except Exception as e:
        raise HTTPException(400, f"Download failed: {e}")
    # Scanned book from Internet Archive? Pull IA's own OCR text right away.
    if ocr.needs_ocr(library.get_text(item["id"])) and ocr.ia_identifier(item.get("source", "")):
        try:
            item = ocr.ocr_item(item["id"])
        except Exception:
            pass
    return item


@app.post("/api/library/{item_id}/ocr")
def lib_ocr(item_id: str, page_from: int = 1, page_to: int = 0):
    if not library.get_item(item_id):
        raise HTTPException(404, "Not found")
    return {"job": _run_job("ocr", lambda job_id, progress: ocr.ocr_item(
        item_id, page_from or 1, page_to, progress))}


@app.post("/api/pdf/upload")
async def pdf_upload(file: UploadFile = File(...)):
    data = await file.read()
    if not data.lstrip()[:5].startswith(b"%PDF"):
        raise HTTPException(400, "Not a PDF file")
    item = library.add_item("pdf", Path(file.filename or "document").stem, source="upload")
    dest = library.LIBRARY_DIR / f"{item['id']}.pdf"
    dest.write_bytes(data)
    pages = pdf_finder.extract_pages(dest)
    library.update_item(item["id"], file=dest.name)
    library.set_text(item["id"], "\f".join(pages))
    return library.update_item(item["id"], meta={"pages": len(pages), "bytes": len(data)})


# ---------- Library ----------
@app.get("/api/library")
def lib_list():
    return {"items": library.list_items()}


@app.get("/api/library/{item_id}")
def lib_get(item_id: str):
    item = library.get_item(item_id)
    if not item:
        raise HTTPException(404, "Not found")
    return {**item, "text": library.get_text(item_id)}


class ScriptReq(BaseModel):
    title: str = "My script"
    text: str


@app.post("/api/library/script")
def lib_add_script(req: ScriptReq):
    return library.add_item("script", req.title, text=req.text, source="typed")


@app.put("/api/library/{item_id}/text")
def lib_set_text(item_id: str, req: ScriptReq):
    if not library.get_item(item_id):
        raise HTTPException(404, "Not found")
    library.set_text(item_id, req.text)
    return library.update_item(item_id, title=req.title)


@app.get("/api/library/{item_id}/file")
def lib_file(item_id: str):
    item = library.get_item(item_id)
    p = library.file_path(item) if item else None
    if not p or not p.exists():
        raise HTTPException(404, "No file")
    return FileResponse(p, media_type="application/pdf", filename=f"{item['title'][:80]}.pdf")


@app.delete("/api/library/{item_id}")
def lib_delete(item_id: str):
    return {"deleted": library.delete_item(item_id)}


# ---------- Video -> script ----------
@app.post("/api/video/transcribe")
async def video_transcribe(url: str = Form(""), language: str = Form(""),
                           file: UploadFile | None = File(None)):
    saved = None
    if file is not None and file.filename:
        saved = TMP_DIR / f"upload_{uuid.uuid4().hex}{Path(file.filename).suffix}"
        with open(saved, "wb") as f:
            shutil.copyfileobj(file.file, f)
    if not url and not saved:
        raise HTTPException(400, "Give a video link or upload a file")

    def fn(job_id, progress):
        try:
            res = transcribe.video_to_script(url=url or None, file=saved, job_id=job_id,
                                             language=language or None, progress=progress)
        finally:
            if saved:
                saved.unlink(missing_ok=True)
        item = library.add_item("transcript", res["title"] or "Video script", text=res["script"],
                                source=url or (file.filename if file else ""),
                                meta={"method": res["method"]})
        return {**res, "item": item}

    return {"job": _run_job("transcribe", fn)}


# ---------- Narration ----------
class NarrateReq(BaseModel):
    text: str = ""
    item_id: str = ""
    page_from: int = 0
    page_to: int = 0
    accent: str = "us"
    gender: str = "auto"
    music: bool = True
    music_volume: float = 0.18
    genre: str = ""
    mood: str = ""
    speed: int = 0


def _select_text(req: NarrateReq) -> str:
    text = req.text or (library.get_text(req.item_id) if req.item_id else "")
    if req.page_from and "\f" in text:
        pages = text.split("\f")
        text = "\n\n".join(pages[req.page_from - 1: (req.page_to or len(pages))])
    return text.strip()


@app.post("/api/analyse")
def analyse(req: NarrateReq):
    text = _select_text(req)
    res = mood.analyse(text[:200000], genre=req.genre or None, mood=req.mood or None)
    counts: dict[str, int] = {}
    for p in res["passages"]:
        counts[p["mood"]] = counts.get(p["mood"], 0) + 1
    words = len(text.split())
    return {"genre": res["genre"], "language": res["language"], "engine": res["engine"],
            "passages": len(res["passages"]), "moods": counts, "words": words,
            "est_minutes": round(words / 150, 1)}


@app.post("/api/narrate")
def narrate_start(req: NarrateReq):
    text = _select_text(req)
    item = library.get_item(req.item_id) if req.item_id else None
    scanned = not text and item and item.get("file")
    if not text and not scanned:
        raise HTTPException(400, "Nothing to read — add text or pick pages")

    def fn(job_id, progress):
        nonlocal text
        if scanned:  # scanned PDF: read the chosen pages with OCR first
            ocr.ocr_item(req.item_id, req.page_from or 1, req.page_to or (req.page_from or 1) + 4,
                         lambda m, f=None: progress(m))
            text = _select_text(req)
            if not text:
                raise RuntimeError("No readable text found on those pages, even after OCR")
        return narrate.narrate(text, job_id, accent=req.accent, gender=req.gender,
                               music_on=req.music, music_volume=req.music_volume,
                               genre=req.genre, force_mood=req.mood, speed=req.speed,
                               progress=progress)

    return {"job": _run_job("narrate", fn)}


@app.get("/api/music/{mood_name}.wav")
def music_preview(mood_name: str, seconds: int = 30):
    if mood_name not in music.STYLES:
        raise HTTPException(404, "Unknown mood")
    path = TMP_DIR / f"preview_{mood_name}_{seconds}.wav"
    if not path.exists():
        music.write_wav(music.render(mood_name, min(120, max(5, seconds))), path)
    return FileResponse(path, media_type="audio/wav")


@app.get("/api/meta")
def meta():
    return {"moods": mood.MOODS, "genres": list(mood.GENRE_MOOD), "accents": list(tts.VOICES),
            "profiles": {m: tts.pick_voice(m)[0] for m in tts.PROFILES}}


@app.get("/audio/{name}")
def audio(name: str):
    p = AUDIO_DIR / Path(name).name
    if not p.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(p, media_type="audio/mpeg")


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
