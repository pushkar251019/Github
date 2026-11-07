"""Long-form video assembler: script -> voiceover -> B-roll per scene -> edit
-> captions -> music. This is how 10-60 min videos are made: no model renders
30 minutes in one shot, so we generate/fetch short visuals and edit them to
the narration.

Script format: paragraphs separated by blank lines = scenes. Optional tag at
the start of a paragraph picks the visual for that scene:
  [broll: ocean waves at dawn]   stock footage search (Pexels/Pixabay)
  [ai: monk meditating, mist]    generate the clip with LTX/Wan
  [library]                      one of your own uploaded B-rolls
  [avatar]                       your face footage lip-synced to the line
No tag = automatic (your library if it has clips, else stock by keywords).
"""
import hashlib
import json
import random
import re
import os
import subprocess
from pathlib import Path

import engines
import stock

ROOT = Path(__file__).parent
LIBRARY = ROOT / "library"
CACHE = ROOT / "cache"
LIBRARY.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
TAG = re.compile(r"^\[(broll|ai|library|avatar)(?::\s*([^\]]*))?\]\s*", re.I)
STOP = set("the a an and or but of to in on at for with is are was were be been this that these those it its "
           "you your we our they their i my me he she his her as by from so not do does did have has had "
           "will would can could just about into than then there here what when where which who how all".split())


def parse(script: str) -> list[dict]:
    scenes = []
    for para in re.split(r"\n\s*\n", script.strip()):
        para = " ".join(para.split())
        if not para:
            continue
        m = TAG.match(para)
        kind, arg = (m.group(1).lower(), (m.group(2) or "").strip()) if m else ("auto", "")
        text = TAG.sub("", para).strip()
        if text:
            scenes.append({"text": text, "visual": kind, "query": arg})
    return scenes


def keywords(text: str, n: int = 4) -> str:
    words = [w for w in re.findall(r"[a-zA-Z]{4,}", text.lower()) if w not in STOP]
    return " ".join(sorted(set(words), key=words.index)[:n]) or "nature landscape"


def run(cmd: list):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"{cmd[0]} failed: {p.stderr[-800:]}")
    return p.stdout


_ENC = None


def encoder() -> list:
    """Pick a video encoder once. STUDIO_ENCODER=auto tries hardware encoders
    (Intel QuickSync, NVIDIA NVENC, AMD AMF) and falls back to libx264.
    Hardware encoding is several times faster on laptops."""
    global _ENC
    if _ENC is None:
        want = os.getenv("STUDIO_ENCODER", "auto")
        opts = {
            "h264_qsv": ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "23"],
            "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"],
            "h264_amf": ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23"],
            "libx264": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21"],
        }
        order = list(opts) if want == "auto" else [want, "libx264"]
        for name in order:
            test = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=256x256:d=0.2",
                                   "-vf", "format=yuv420p", *opts[name], "-f", "null", "-"],
                                  capture_output=True)
            if test.returncode == 0:
                _ENC = opts[name]
                break
    return _ENC


def duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(path)]).strip())


class Builder:
    def __init__(self, opts: dict, workdir: Path, progress):
        self.o = opts
        self.dir = workdir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.progress = progress
        portrait = opts.get("orientation") == "portrait"
        self.w, self.h = (1080, 1920) if portrait else (1920, 1080)
        self.orient = "portrait" if portrait else "landscape"
        self.used: set[str] = set()
        self.library = sorted(p for p in LIBRARY.iterdir() if p.suffix.lower() in VIDEO_EXT | IMAGE_EXT)
        random.Random(opts.get("seed", 0)).shuffle(self.library)
        self.lib_i = 0

    # ---- voice
    def voice(self, i, text) -> Path:
        out = self.dir / f"v{i:04}.wav"
        if self.o.get("reference"):
            engines.clone(text, Path(self.o["reference"]), self.o.get("exaggeration", 0.5), out)
        else:
            engines.tts(text, self.o.get("voice", "af_heart"), self.o.get("speed", 1.0), out)
        return out

    # ---- visuals
    def visual(self, i, scene, audio: Path, dur: float) -> tuple[Path | None, bool]:
        """Returns (source clip/image, already_lipsynced)."""
        kind, q = scene["visual"], scene["query"]
        if kind == "auto":
            kind = "library" if self.library else "broll"
        try:
            if kind == "avatar" and self.o.get("face"):
                out = self.dir / f"avatar{i:04}.mp4"
                return engines.lipsync(Path(self.o["face"]), audio, out), True
            if kind == "ai":
                out = self.dir / f"ai{i:04}.mp4"
                return engines.video(q or scene["text"][:200], self.o.get("ai_model", "ltx"),
                                     min(10, max(3, int(dur))), None, out), False
            if kind == "library" and self.library:
                clip = self.library[self.lib_i % len(self.library)]
                self.lib_i += 1
                return clip, False
            return self.stock_clip(q or keywords(scene["text"])), False
        except Exception as e:
            self.progress(note=f"scene {i + 1}: visual failed ({e}); using fallback")
            return (self.library[i % len(self.library)] if self.library else None), False

    def stock_clip(self, query: str) -> Path | None:
        for kind in ("video", "photo"):
            for r in stock.search(query, kind, self.orient, n=10):
                if r["download"] in self.used:
                    continue
                self.used.add(r["download"])
                ext = ".mp4" if kind == "video" else ".jpg"
                name = hashlib.sha1(r["download"].encode()).hexdigest()[:16] + ext
                self.credits.append(f'{r["source"]}: {r["credit"]} - {r["page"]}')
                return stock.download(r["download"], CACHE / name)
        return None

    # ---- render one scene to a uniform mp4 segment
    def segment(self, i, src: Path | None, audio: Path, dur: float, synced: bool) -> Path:
        out = self.dir / f"s{i:04}.mp4"
        w, h = self.w, self.h
        fit = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30"
        if src is None:
            inp = ["-f", "lavfi", "-i", f"color=c=0x101418:s={w}x{h}:r=30"]
            vf = "format=yuv420p"
        elif src.suffix.lower() in IMAGE_EXT:  # slow Ken Burns zoom on stills
            frames = int(dur * 30) + 30
            inp = ["-loop", "1", "-i", str(src)]
            bw, bh = w * 3 // 2, h * 3 // 2
            vf = (f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
                  f"zoompan=z='min(1+0.0008*on,1.25)':d={frames}:s={w}x{h}:fps=30"
                  f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',format=yuv420p")
        else:
            start = 0.0
            if not synced:  # random start inside long B-rolls so reuse looks different
                try:
                    slack = duration(src) - dur
                    start = random.uniform(0, slack) if slack > 1 else 0.0
                except Exception:
                    pass
            inp = ["-stream_loop", "-1", "-ss", f"{start:.2f}", "-i", str(src)]
            vf = fit + ",format=yuv420p"
        run(["ffmpeg", "-y", "-v", "error", *inp, "-i", str(audio), "-map", "0:v", "-map", "1:a",
             "-vf", vf, "-t", f"{dur:.3f}", *encoder(),
             "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", str(out)])
        return out

    # ---- captions from the script itself (exact wording, no ASR errors)
    @staticmethod
    def srt(scenes, durs, words_per_line=7) -> str:
        def ts(t):
            ms = int(round(t * 1000))
            return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
        out, n, t0 = [], 1, 0.0
        for sc, d in zip(scenes, durs):
            words = sc["text"].split()
            chunks = [words[k:k + words_per_line] for k in range(0, len(words), words_per_line)]
            per = d / max(1, len(words))
            t = t0
            for c in chunks:
                out.append(f"{n}\n{ts(t)} --> {ts(t + per * len(c))}\n{' '.join(c)}\n")
                t += per * len(c)
                n += 1
            t0 += d
        return "\n".join(out)

    def build(self, script: str, out: Path) -> Path:
        scenes = parse(script)
        if not scenes:
            raise ValueError("Script has no text")
        self.credits: list[str] = []
        segs, durs = [], []
        total = len(scenes)
        for i, sc in enumerate(scenes):
            self.progress(pct=int(90 * i / total), note=f"scene {i + 1}/{total}")
            audio = self.voice(i, sc["text"])
            d = duration(audio) + 0.25  # small breath between scenes
            src, synced = self.visual(i, sc, audio, d)
            segs.append(self.segment(i, src, audio, d, synced))
            durs.append(d)

        self.progress(pct=92, note="joining scenes")
        lst = self.dir / "list.txt"
        lst.write_text("".join(f"file '{s.name}'\n" for s in segs))
        joined = self.dir / "joined.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
             "-c", "copy", str(joined)])

        srt_path = out.with_suffix(".srt")
        srt_path.write_text(self.srt(scenes, durs))

        self.progress(pct=95, note="captions + music")
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(joined)]
        music = self.o.get("music")
        if music:
            cmd += ["-stream_loop", "-1", "-i", str(music)]
        vf = []
        if self.o.get("burn_captions"):
            size = 14 if self.orient == "portrait" else 18
            vf = ["-vf", f"subtitles={srt_path.name}:force_style='Fontsize={size},Outline=2,"
                         f"BorderStyle=1,MarginV={60 if self.orient == 'portrait' else 40}'"]
        if music:  # duck music under the voice
            af = ("[1:a]volume=0.35[m];[0:a]asplit[v1][v2];[m][v1]sidechaincompress=threshold=0.03:"
                  "ratio=10:attack=20:release=400[d];[v2][d]amix=inputs=2:duration=first:normalize=0[a]")
            cmd += ["-filter_complex", af, "-map", "0:v", "-map", "[a]"]
        cmd += vf + (encoder() if vf else ["-c:v", "copy"])
        cmd += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
        subprocess_cwd_run(cmd, cwd=out.parent)
        if self.credits:
            out.with_suffix(".credits.txt").write_text("\n".join(dict.fromkeys(self.credits)))
        self.progress(pct=100, note=f"done: {sum(durs) / 60:.1f} min, {total} scenes")
        return out


def subprocess_cwd_run(cmd, cwd):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if p.returncode:
        raise RuntimeError(f"ffmpeg failed: {p.stderr[-800:]}")
