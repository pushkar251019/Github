"""Mood-aware text-to-speech.

Primary engine: Microsoft Edge neural voices via `edge-tts` (free, natural,
needs internet). Offline fallback: espeak-ng (robotic but works anywhere).
Each mood maps to a voice + prosody (speed, pitch, volume)."""
import asyncio
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import TTS_ENGINE

SR = 24000  # all audio in the pipeline is 24 kHz mono

VOICES = {  # accent -> gender -> list of voices (variants used per mood)
    "us": {"f": ["en-US-JennyNeural", "en-US-AriaNeural", "en-US-MichelleNeural", "en-US-AnaNeural"],
           "m": ["en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-AndrewNeural", "en-US-EricNeural"]},
    "gb": {"f": ["en-GB-SoniaNeural", "en-GB-LibbyNeural", "en-GB-MaisieNeural"],
           "m": ["en-GB-RyanNeural", "en-GB-ThomasNeural"]},
    "in": {"f": ["en-IN-NeerjaNeural"], "m": ["en-IN-PrabhatNeural"]},
    "hi": {"f": ["hi-IN-SwaraNeural"], "m": ["hi-IN-MadhurNeural"]},
}


@dataclass(frozen=True)
class Profile:
    gender: str      # default narrator gender for this mood
    variant: int     # which voice in the accent list
    rate: int        # % speed change
    pitch: int       # Hz change
    volume: int      # % volume change
    pause: float     # seconds of silence after each passage


PROFILES = {
    "calm":          Profile("f", 0, -10, -2, 0, 0.9),
    "joyful":        Profile("f", 0, +8, +4, +5, 0.5),
    "sad":           Profile("f", 1, -16, -5, -8, 1.1),
    "suspense":      Profile("m", 0, -6, -4, 0, 0.8),
    "horror":        Profile("m", 1, -18, -9, -5, 1.2),
    "romantic":      Profile("f", 2, -12, -1, -5, 0.9),
    "epic":          Profile("m", 1, -2, -6, +10, 0.7),
    "mystery":       Profile("m", 0, -8, -3, -3, 0.9),
    "inspirational": Profile("m", 2, -4, -1, +5, 0.8),
    "whimsical":     Profile("f", 3, +4, +6, 0, 0.6),
    "informative":   Profile("f", 0, 0, 0, 0, 0.5),
}


def pick_voice(mood: str, accent: str = "us", gender: str = "auto") -> tuple[str, Profile]:
    prof = PROFILES.get(mood, PROFILES["calm"])
    g = prof.gender if gender == "auto" else gender
    pool = VOICES.get(accent, VOICES["us"])[g]
    return pool[prof.variant % len(pool)], prof


def _signed(n: int, unit: str) -> str:
    return f"{'+' if n >= 0 else '-'}{abs(n)}{unit}"


async def _edge(text: str, voice: str, prof: Profile, out_mp3: Path, speed: int) -> None:
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=_signed(prof.rate + speed, "%"),
                                pitch=_signed(prof.pitch, "Hz"), volume=_signed(prof.volume, "%"))
    await comm.save(str(out_mp3))


def _espeak(text: str, prof: Profile, gender: str, lang: str, out_wav: Path, speed: int) -> None:
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("No TTS engine available (install espeak-ng or allow internet for edge-tts)")
    wpm = int(165 * (1 + (prof.rate + speed) / 100))
    pitch = max(0, min(99, 50 + prof.pitch * 3))
    voice = f"{'hi' if lang == 'hi' else 'en'}+{'f3' if gender == 'f' else 'm3'}"
    subprocess.run([exe, "-v", voice, "-s", str(wpm), "-p", str(pitch), "-w", str(out_wav), text],
                   check=True, capture_output=True)


def to_wav(src: Path, dst: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1",
                    "-ar", str(SR), "-sample_fmt", "s16", str(dst)], check=True)


_edge_ok: bool | None = None  # remember if edge-tts works this session


def synthesize(text: str, mood: str, out_wav: Path, *, accent: str = "us",
               gender: str = "auto", lang: str = "en", speed: int = 0) -> dict:
    """Render one passage to a 24 kHz mono wav. Returns voice info used."""
    global _edge_ok
    if lang == "hi":
        accent = "hi"
    voice, prof = pick_voice(mood, accent, gender)
    g = prof.gender if gender == "auto" else gender
    engine = TTS_ENGINE
    if engine in ("auto", "edge") and _edge_ok is not False:
        mp3 = out_wav.with_suffix(".mp3")
        try:
            asyncio.run(_edge(text, voice, prof, mp3, speed))
            if mp3.stat().st_size == 0:
                raise RuntimeError("edge-tts returned no audio")
            to_wav(mp3, out_wav)
            mp3.unlink(missing_ok=True)
            _edge_ok = True
            return {"engine": "edge", "voice": voice, "pause": prof.pause}
        except Exception:
            mp3.unlink(missing_ok=True)
            if engine == "edge":
                raise
            _edge_ok = False
    raw = out_wav.with_suffix(".raw.wav")
    _espeak(text, prof, g, lang, raw, speed)
    to_wav(raw, out_wav)
    raw.unlink(missing_ok=True)
    return {"engine": "espeak", "voice": f"espeak-{g}", "pause": prof.pause}
