"""Video -> script. Tries the video's own captions first (fast, free), then
falls back to local speech recognition with faster-whisper."""
import re
import shutil
import subprocess
from pathlib import Path

from .config import TMP_DIR, WHISPER_MODEL

_whisper = None


def _get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(WHISPER_MODEL, device="auto", compute_type="int8")
    return _whisper


def _ydl_opts(job_dir: Path, **extra) -> dict:
    return {"outtmpl": str(job_dir / "media.%(ext)s"), "quiet": True,
            "no_warnings": True, "noplaylist": True, **extra}


def fetch_captions(url: str, job_dir: Path, lang: str = "en") -> tuple[str, str]:
    """Download subtitles (manual or auto) via yt-dlp. Returns (title, text)."""
    import yt_dlp
    opts = _ydl_opts(job_dir, skip_download=True, writesubtitles=True,
                     writeautomaticsub=True, subtitleslangs=[lang, f"{lang}.*"],
                     subtitlesformat="vtt")
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    vtts = sorted(job_dir.glob("*.vtt"))
    if not vtts:
        return info.get("title", ""), ""
    return info.get("title", ""), vtt_to_text(vtts[0].read_text("utf-8", "ignore"))


def download_audio(url: str, job_dir: Path) -> tuple[str, Path]:
    import yt_dlp
    with yt_dlp.YoutubeDL(_ydl_opts(job_dir, format="bestaudio/best")) as ydl:
        info = ydl.extract_info(url, download=True)
    files = [p for p in job_dir.glob("media.*") if p.suffix != ".vtt"]
    if not files:
        raise RuntimeError("Could not download audio from that link")
    return info.get("title", "Video"), files[0]


def vtt_to_text(vtt: str) -> str:
    """Convert WebVTT captions into deduplicated plain text (auto-captions
    repeat each line several times as it scrolls)."""
    lines, last = [], ""
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) \
                or "-->" in line or line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\[(music|applause|laughter)\]", "", line, flags=re.I).strip()
        if line and line != last and not (last and last.endswith(line)):
            lines.append(line)
            last = line
    words = " ".join(lines).split()
    # remove rolling overlap duplicates like "a b c" "b c d"
    return " ".join(words)


def transcribe_file(path: Path, language: str | None = None) -> list[dict]:
    model = _get_whisper()
    wav = path.with_suffix(".16k.wav")
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
                        "-ac", "1", "-ar", "16000", str(wav)], check=True)
        path = wav
    segments, _info = model.transcribe(str(path), language=language, vad_filter=True)
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]


def segments_to_script(segments: list[dict], pause: float = 1.5) -> str:
    """Group whisper segments into readable paragraphs, breaking on long pauses
    or every ~6 sentences."""
    paras, cur, sentences, prev_end = [], [], 0, None
    for s in segments:
        if prev_end is not None and (s["start"] - prev_end > pause or sentences >= 6) and cur:
            paras.append(" ".join(cur))
            cur, sentences = [], 0
        cur.append(s["text"])
        sentences += len(re.findall(r"[.!?]", s["text"]))
        prev_end = s["end"]
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras)


def paragraphize(text: str, per: int = 5) -> str:
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    return "\n\n".join(" ".join(sents[i:i + per]) for i in range(0, len(sents), per))


def video_to_script(*, url: str | None = None, file: Path | None = None,
                    job_id: str, language: str | None = None, progress=lambda m: None) -> dict:
    job_dir = TMP_DIR / f"video_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        title, method = "Video", "whisper"
        if url:
            progress("Looking for captions…")
            try:
                title, text = fetch_captions(url, job_dir, language or "en")
            except Exception:
                text = ""
            if len(text.split()) > 30:
                return {"title": title, "script": paragraphize(text), "method": "captions"}
            progress("No captions — downloading audio…")
            title, file = download_audio(url, job_dir)
        if not file:
            raise ValueError("Provide a video URL or file")
        progress("Transcribing speech (this can take a while)…")
        segs = transcribe_file(Path(file), language)
        return {"title": title, "script": segments_to_script(segs), "method": method,
                "segments": segs}
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
