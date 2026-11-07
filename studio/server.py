"""Studio: a self-hosted voice/image/video generator. Run: python server.py"""
import queue
import shutil
import threading
import time
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import engines
import longform
import stock

ROOT = Path(__file__).parent
OUT = ROOT / "outputs"
UPLOADS = ROOT / "uploads"
OUT.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)

app = FastAPI(title="Studio")
jobs: dict[str, dict] = {}
work: "queue.Queue[tuple[str, callable]]" = queue.Queue()


def worker():
    """One GPU, one job at a time: jobs run in submission order."""
    while True:
        job_id, fn = work.get()
        job = jobs[job_id]
        job.update(status="running", started=time.time())
        try:
            job["file"] = fn(job).name
            job["status"] = "done"
        except Exception as e:  # surface model errors to the UI
            traceback.print_exc()
            job.update(status="error", error=f"{type(e).__name__}: {e}")
        job["finished"] = time.time()


threading.Thread(target=worker, daemon=True).start()


def submit(kind: str, ext: str, fn) -> dict:
    job_id = uuid.uuid4().hex[:12]
    out = OUT / f"{kind}-{job_id}.{ext}"
    jobs[job_id] = {"id": job_id, "kind": kind, "status": "queued", "created": time.time()}
    work.put((job_id, lambda job: fn(out, job)))
    return jobs[job_id]


def save_upload(f: UploadFile | None) -> Path | None:
    if not f or not f.filename:
        return None
    path = UPLOADS / f"{uuid.uuid4().hex[:8]}{Path(f.filename).suffix.lower()}"
    with path.open("wb") as dst:
        shutil.copyfileobj(f.file, dst)
    return path


def need_text(text: str) -> str:
    text = text.strip()
    if not text:
        raise HTTPException(400, "Text/prompt is empty")
    return text


@app.get("/api/info")
def info():
    try:
        dev = engines.device()
    except ImportError:
        dev = "unknown (torch not installed)"
    return {"device": dev, "fake": engines.FAKE, "voices": engines.KOKORO_VOICES}


@app.post("/api/tts")
def tts(text: str = Form(...), voice: str = Form("af_heart"), speed: float = Form(1.0)):
    if voice not in engines.KOKORO_VOICES:
        raise HTTPException(400, "Unknown voice")
    text = need_text(text)
    return submit("voice", "wav", lambda out, job: engines.tts(text, voice, speed, out))


@app.post("/api/clone")
def clone(text: str = Form(...), exaggeration: float = Form(0.5),
          reference: UploadFile = File(...)):
    text = need_text(text)
    ref = save_upload(reference)
    if not ref:
        raise HTTPException(400, "Reference audio required")
    return submit("clone", "wav", lambda out, job: engines.clone(text, ref, exaggeration, out))


@app.post("/api/image")
def image(prompt: str = Form(...), width: int = Form(1024), height: int = Form(1024),
          seed: int = Form(0)):
    prompt = need_text(prompt)
    width, height = (max(256, min(1536, v)) // 16 * 16 for v in (width, height))
    return submit("image", "png", lambda out, job: engines.image(prompt, width, height, seed, out))


@app.post("/api/video")
def video(prompt: str = Form(...), model: str = Form("ltx"), seconds: int = Form(5),
          start_image: UploadFile | None = File(None)):
    prompt = need_text(prompt)
    if model not in ("ltx", "wan"):
        raise HTTPException(400, "model must be ltx or wan")
    img = save_upload(start_image)
    seconds = max(2, min(10, seconds))
    return submit("video", "mp4", lambda out, job: engines.video(prompt, model, seconds, img, out))


@app.post("/api/captions")
def captions(media: UploadFile = File(...)):
    path = save_upload(media)
    if not path:
        raise HTTPException(400, "Media file required")
    return submit("captions", "srt", lambda out, job: engines.captions(path, out))


@app.get("/api/jobs")
def list_jobs():
    return sorted(jobs.values(), key=lambda j: j["created"], reverse=True)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "No such job")
    return jobs[job_id]


@app.get("/outputs/{name}")
def output(name: str):
    path = (OUT / name).resolve()
    if path.parent != OUT.resolve() or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


@app.post("/api/longform")
def make_longform(script: str = Form(...), orientation: str = Form("landscape"),
                  voice: str = Form("af_heart"), speed: float = Form(1.0),
                  ai_model: str = Form("ltx"), burn_captions: bool = Form(True),
                  reference: UploadFile | None = File(None), face: UploadFile | None = File(None),
                  music: UploadFile | None = File(None)):
    """Script of any length -> finished narrated video (10-60+ min is fine)."""
    script = need_text(script)
    if not longform.parse(script):
        raise HTTPException(400, "Script has no text")
    opts = dict(orientation=orientation, voice=voice, speed=speed, ai_model=ai_model,
                burn_captions=burn_captions, reference=save_upload(reference),
                face=save_upload(face), music=save_upload(music))

    def run(out, job):
        def progress(pct=None, note=None):
            if pct is not None:
                job["progress"] = pct
            if note:
                job["note"] = note
        return longform.Builder(opts, ROOT / "work" / out.stem, progress).build(script, out)

    return submit("longform", "mp4", run)


@app.get("/api/stock")
def stock_search(q: str, kind: str = "video", orientation: str = "landscape"):
    """Royalty-free search with direct download links (Pexels/Pixabay; music = links)."""
    try:
        return stock.search(q, kind, orientation)
    except Exception as e:
        raise HTTPException(502, str(e))


@app.post("/api/library")
def add_to_library(files: list[UploadFile] = File(...)):
    """Your own B-roll: used for 'library' scenes in long-form videos."""
    saved = []
    for f in files:
        name = Path(f.filename or "").name
        if Path(name).suffix.lower() not in longform.VIDEO_EXT | longform.IMAGE_EXT:
            continue
        with (longform.LIBRARY / name).open("wb") as dst:
            shutil.copyfileobj(f.file, dst)
        saved.append(name)
    return {"saved": saved}


@app.get("/api/library")
def list_library():
    return sorted(p.name for p in longform.LIBRARY.iterdir() if not p.name.startswith("."))


app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7860)
