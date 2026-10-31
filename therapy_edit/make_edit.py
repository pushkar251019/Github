#!/usr/bin/env python3
"""Therapy reel assembler.

Usage:
  python3 make_edit.py MY_VIDEO.mp4 [--music track.mp3 --music-start 32.5] [--bpm 128]
                       [--quote "..."] [--out final.mp4]

Structure: intro.mp4 (hook + heartbeat to flatline) -> beat-synced main video
with "This is the therapy I need." and a closing quote.
- With --music: beats are auto-detected from the track; music drops exactly
  when your footage starts. Use --music-start to begin at the drop of the song.
- Without --music: beat grid from --bpm, and you add the song later in
  Instagram/CapCut, aligned at 7.0s (the moment the footage starts).
"""
import argparse, json, subprocess, sys, numpy as np, os

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
INTRO = os.path.join(HERE, "intro.mp4")
INTRO_LEN = 7.0


def run(cmd):
    print(" ".join(cmd[:6]), "...")
    subprocess.run(cmd, check=True)


def duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "json", path])
    return float(json.loads(out)["format"]["duration"])


def detect_beats(music, start, length):
    """Onset-energy tempo estimate + phase alignment; returns beat times (s, relative)."""
    sr = 22050
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(length),
                                   "-i", music, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"])
    x = np.frombuffer(raw, np.float32)
    hop = 512
    frames = len(x) // hop
    e = np.array([np.sum(x[i*hop:(i+1)*hop] ** 2) for i in range(frames)])
    onset = np.maximum(0, np.diff(np.log1p(e * 1000), prepend=0))
    fps = sr / hop
    ac = np.correlate(onset, onset, "full")[len(onset)-1:]
    lags = np.arange(len(ac)) / fps
    valid = (lags > 60/180) & (lags < 60/80)
    period = lags[valid][np.argmax(ac[valid])]
    p = int(round(period * fps))
    phase = max(range(p), key=lambda k: onset[k::p].sum())
    beats = np.arange(phase / fps, length, period)
    print(f"Detected tempo ≈ {60/period:.1f} BPM")
    return beats


def esc(s):
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--music")
    ap.add_argument("--music-start", type=float, default=0.0)
    ap.add_argument("--bpm", type=float, default=128.0)
    ap.add_argument("--quote", default="Some people search for peace.\nI found mine right here.")
    ap.add_argument("--keep-original-audio", type=float, default=0.0,
                    help="volume 0-1 of the clip's own sound under the music")
    ap.add_argument("--out", default=os.path.join(HERE, "therapy_final.mp4"))
    a = ap.parse_args()

    L = duration(a.video)
    beats = detect_beats(a.music, a.music_start, L) if a.music else np.arange(0, L, 60 / a.bpm)
    # Punch-zoom on every 2nd beat, white flash every 8th beat (downbeats of phrases)
    punch = beats[::2]
    flash = beats[::8][1:]
    zoom = "+".join(f"0.06*between(t,{b:.3f},{b+0.12:.3f})*(1-(t-{b:.3f})/0.12)" for b in punch) or "0"
    fl = "+".join(f"between(t,{b:.3f},{b+0.08:.3f})" for b in flash) or "0"

    q_start = max(3.5, L - 4.5)
    tag = esc("This is the therapy I need.")
    quote_lines = [esc(s) for s in a.quote.split("\n")]
    qdraw = ",".join(
        f"drawtext=fontfile={FONT}:text='{ln}':fontcolor=white:fontsize=64:borderw=3:bordercolor=black@0.6:"
        f"x=(w-tw)/2:y=h*0.72+{i*84}:alpha='min(1,max(0,(t-{q_start+0.3*i:.2f})/0.5))'"
        for i, ln in enumerate(quote_lines))

    vmain = (
        f"[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,"
        f"eq=contrast=1.08:saturation=1.15,"
        f"scale=w='trunc(1080*(1+{zoom})/2)*2':h='trunc(1920*(1+{zoom})/2)*2':eval=frame,crop=1080:1920,"
        f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.55:t=fill:enable='{fl}',"
        f"drawtext=fontfile={FONT}:text='{tag}':fontcolor=white:fontsize=78:borderw=3:bordercolor=black@0.6:"
        f"x=(w-tw)/2:y=h*0.16:alpha='min(1,t/0.4)*min(1,max(0,(3.6-t)/0.5))',"
        f"{qdraw},vignette=PI/5,format=yuv420p[vm]"
    )
    xf = 0.4  # intro -> footage transition lands on the flatline
    filt = [f"[0:v]fps=30,setsar=1,format=yuv420p[vi]", vmain,
            f"[vi][vm]xfade=transition=circleopen:duration={xf}:offset={INTRO_LEN - xf}[v]"]
    inputs = ["-i", INTRO, "-i", a.video]
    total = INTRO_LEN - xf + L
    amix = [f"[0:a]aresample=48000,apad=whole_dur={total}[ai]"]
    srcs = "[ai]"
    n = 1
    if a.music:
        inputs += ["-ss", str(a.music_start), "-i", a.music]
        amix.append(f"[2:a]aresample=48000,atrim=0:{L},afade=t=in:d=0.05,afade=t=out:st={L-2}:d=2,"
                    f"adelay={int((INTRO_LEN - xf)*1000)}:all=1[am]")
        srcs += "[am]"; n += 1
    if a.keep_original_audio > 0:
        amix.append(f"[1:a]aresample=48000,volume={a.keep_original_audio},"
                    f"adelay={int((INTRO_LEN - xf)*1000)}:all=1[ao]")
        srcs += "[ao]"; n += 1
    amix.append(f"{srcs}amix=inputs={n}:normalize=0:duration=longest,alimiter=limit=0.95[a]")
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
         "-filter_complex", ";".join(filt + amix), "-map", "[v]", "-map", "[a]",
         "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out])
    print("Done ->", a.out)


if __name__ == "__main__":
    main()
