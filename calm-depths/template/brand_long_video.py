#!/usr/bin/env python3
"""Brand a full-length ambience video: optional intro in front (1.5 s crossfade),
permanent corner watermark, and the subscribe animation roughly every 60 s.

  python3 template/brand_long_video.py main.mp4 out.mp4 --intro exports/CalmDepths_Intro_ocean.mp4
"""
import argparse, json, os, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BR = os.path.join(ROOT, "assets", "brand")


def dur(p):
    return float(json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                      "-of", "json", p]))["format"]["duration"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("main"); ap.add_argument("out"); ap.add_argument("--intro")
    ap.add_argument("--xfade", type=float, default=1.5)
    a = ap.parse_args()
    wm = os.path.join(BR, "CalmDepths_Watermark_transparent.png")
    cyc = os.path.join(BR, "CalmDepths_Subscribe_60s_cycle_alpha.mov")
    norm = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"
    # main video gets the watermark + periodic subscribe (clock starts at main video start)
    fc = [f"[0:v]{norm}[m0]",
          "[1:v]format=rgba,colorchannelmixer=aa=0.72[wm]",
          "[m0][wm]overlay=W-w-48:H-h-40:shortest=1:format=auto[m1]",
          "[2:v]format=rgba[sb]",
          "[m1][sb]overlay=(W-w)/2:H-h-70:shortest=1:format=auto[mv]",
          "[0:a]aresample=48000[ma]"]
    inputs = ["-i", a.main, "-loop", "1", "-i", wm, "-stream_loop", "-1", "-i", cyc]
    vout, aout = "[mv]", "[ma]"
    total = dur(a.main)
    if a.intro:
        inputs += ["-i", a.intro]; off = dur(a.intro) - a.xfade
        fc += [f"[3:v]{norm}[iv]", f"[iv][mv]xfade=transition=fade:duration={a.xfade}:offset={off:.3f}[v]",
               f"[3:a]aresample=48000[ia]", f"[ia][ma]acrossfade=d={a.xfade}[a]"]
        vout, aout = "[v]", "[a]"
        total += off
    subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", vout, "-map", aout, "-t", f"{total:.3f}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", a.out], check=True)


if __name__ == "__main__":
    main()
