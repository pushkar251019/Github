#!/usr/bin/env python3
"""Calm Depths — background builder.
Cuts the theme's shots, stabilises, slows (frame-blended), grades, and crossfades
them into a 1920x1080 / 30 fps clean plate of at least `--duration` seconds.
Only this step (and the ambience) changes between themes."""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(cmd):
    print(" ".join(cmd[:6]), "...", flush=True)
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default="ocean")
    ap.add_argument("--duration", type=float, default=45.0)
    a = ap.parse_args()
    th = json.load(open(os.path.join(ROOT, "template", "themes", a.theme + ".json")))
    src = os.path.join(ROOT, th["footage"])
    work = os.path.join(ROOT, "work", a.theme); os.makedirs(work, exist_ok=True)
    trf = os.path.join(work, "stab.trf")
    if th.get("stabilise") and not os.path.exists(trf):
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf",
             f"vidstabdetect=shakiness=6:accuracy=15:result={trf}", "-f", "null", "-"])
    sp = th.get("speed", 1.0)
    base = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"
    stab = f"vidstabtransform=input={trf}:smoothing=45:zoom=4:optzoom=0:interpol=bicubic," if th.get("stabilise") else ""
    vign = "vignette=angle=0.55:mode=forward"
    parts = []
    for i, s in enumerate(th["shots"]):
        out = os.path.join(work, f"shot{i}.mp4"); parts.append(out)
        # stabilise on full timeline (trf is indexed by frame), then trim, slow, blend
        vf = (f"{stab}{base},trim=start={s['start']}:end={s['end']},setpts=(PTS-STARTPTS)/{sp},"
              f"framerate=fps=30:interp_start=0:interp_end=255:scene=100,"
              f"{th['grade']},{vign},format=yuv420p")
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-an", "-vf", vf,
             "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-r", "30", out])
    # crossfade chain
    xf = th.get("crossfade", 1.5)
    durs = [(s["end"] - s["start"]) / sp for s in th["shots"]]
    inputs, fc, prev, off = [], [], "[0:v]", 0.0
    for p in parts: inputs += ["-i", p]
    for i in range(1, len(parts)):
        off += durs[i - 1] - xf
        lab = f"[x{i}]"
        fc.append(f"{prev}[{i}:v]xfade=transition=fade:duration={xf}:offset={off:.3f}{lab}")
        prev = lab
    total = sum(durs) - xf * (len(parts) - 1)
    print(f"background length {total:.2f}s (need {a.duration})")
    if total < a.duration:
        sys.exit("Not enough footage: add or lengthen shots in the theme file.")
    fc.append(f"{prev}trim=duration={a.duration},fade=t=in:st=0:d=1.2,format=yuv420p[v]")
    out = os.path.join(work, "background.mp4")
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-r", "30", out])
    print("wrote", out)

if __name__ == "__main__":
    main()
