"""Script -> narrated MP3 with mood-matched voices and optional music bed."""
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

from . import mood as mood_mod
from . import music, tts
from .config import AUDIO_DIR, TMP_DIR


def _read_wav(p: Path) -> np.ndarray:
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768


def narrate(text: str, job_id: str, *, accent: str = "us", gender: str = "auto",
            music_on: bool = True, music_volume: float = 0.18, genre: str | None = None,
            force_mood: str | None = None, speed: int = 0, progress=lambda m, f=None: None) -> dict:
    analysis = mood_mod.analyse(text, genre=genre or None, mood=force_mood or None)
    passages = analysis["passages"]
    if not passages:
        raise ValueError("There is no text to read")
    work = TMP_DIR / f"narr_{job_id}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        voice_parts, timeline, music_segments = [], [], []
        t = 0.0
        for i, p in enumerate(passages):
            progress(f"Voicing passage {i + 1}/{len(passages)} ({p['mood']})", i / len(passages))
            wav = work / f"p{i:05d}.wav"
            info = tts.synthesize(p["text"], p["mood"], wav, accent=accent, gender=gender,
                                  lang=analysis["language"], speed=speed)
            audio = _read_wav(wav)
            silence = np.zeros(int(info["pause"] * tts.SR), np.float32)
            dur = (len(audio) + len(silence)) / tts.SR
            voice_parts += [audio, silence]
            timeline.append({"start": round(t, 2), "end": round(t + dur, 2), "mood": p["mood"],
                             "voice": info["voice"], "engine": info["engine"], "text": p["text"]})
            music_segments.append((p["mood"], dur))
            t += dur
            wav.unlink(missing_ok=True)

        lead = np.zeros(int(1.0 * tts.SR), np.float32)  # 1 s music intro
        voice = np.concatenate([lead] + voice_parts + [lead])
        for seg in timeline:
            seg["start"] += 1.0
            seg["end"] += 1.0
        voice_wav = work / "voice.wav"
        music.write_wav(voice, voice_wav)
        out = AUDIO_DIR / f"{job_id}.mp3"

        progress("Mixing audio…", 0.97)
        if music_on:
            segs = [(passages[0]["mood"], 1.0)] + music_segments + [(passages[-1]["mood"], 1.0)]
            bed = music.render_timeline(segs)[: len(voice)]
            music_wav = work / "music.wav"
            music.write_wav(bed, music_wav)
            vol = max(0.0, min(1.0, music_volume)) * 2.0
            filt = (f"[1:a]volume={vol:.3f}[m];"
                    "[m][0:a]sidechaincompress=threshold=0.03:ratio=5:attack=30:release=600[duck];"
                    "[0:a][duck]amix=inputs=2:duration=first:normalize=0,"
                    "afade=t=out:st={st}:d=1[out]").format(st=max(0, len(voice) / tts.SR - 1))
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice_wav), "-i", str(music_wav),
                   "-filter_complex", filt, "-map", "[out]", "-b:a", "128k", str(out)]
        else:
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice_wav), "-b:a", "128k", str(out)]
        subprocess.run(cmd, check=True, capture_output=True)
        return {"audio": f"/audio/{out.name}", "duration": round(len(voice) / tts.SR, 1),
                "genre": analysis["genre"], "language": analysis["language"],
                "mood_engine": analysis["engine"], "timeline": timeline}
    finally:
        shutil.rmtree(work, ignore_errors=True)
