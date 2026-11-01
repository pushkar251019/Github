#!/usr/bin/env python3
"""Final reel: intro (hook + heartbeat) -> beat-cut drive footage with text + quote.

python3 render_reel.py PREP.mp4 --intro-audio heartbeat_B_pure.wav --bpm 128 --out reel.mp4
PREP.mp4 = source already scaled to 1080x1920 @30fps.
Cuts land every 4 beats; each cut gets a zoom punch, every 2nd cut a white flash,
and a smaller punch on the off-bar beat. Footage starts at 6.6s in the final reel:
start the song's drop there when adding music in Instagram/CapCut.
"""
import argparse, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SERIF_I = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
SERIF_B = "/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prep")
    ap.add_argument("--intro-audio", default=os.path.join(HERE, "heartbeat_B_pure.wav"))
    ap.add_argument("--bpm", type=float, default=128)
    ap.add_argument("--segments", type=int, default=12)
    ap.add_argument("--beats-per-cut", type=int, default=4)
    ap.add_argument("--src-len", type=float, default=37.0)
    ap.add_argument("--road-volume", type=float, default=0.35)
    ap.add_argument("--quote", default="Open road. Loud music. Clear mind.")
    ap.add_argument("--out", default=os.path.join(HERE, "therapy_reel.mp4"))
    a = ap.parse_args()

    beat = 60 / a.bpm
    seg = beat * a.beats_per_cut
    n = a.segments
    starts = [round(i * (a.src_len - seg - 0.3) / (n - 1), 3) for i in range(n)]
    main_len = seg * n
    xf = 0.4
    intro_len = 7.0
    off = intro_len - xf

    f = ["[0:v]fps=30,settb=1/30,setsar=1,format=yuv420p[vi]"]
    cat = ""
    for i, s in enumerate(starts):
        z = f"1+0.14*max(0\\,1-t/0.22)+0.05*between(t\\,{2*beat:.4f}\\,{2*beat+0.15:.4f})*(1-(t-{2*beat:.4f})/0.15)"
        flash = f",drawbox=x=0:y=0:w=iw:h=ih:color=white@0.6:t=fill:enable='lt(t,0.07)'" if i % 2 else ""
        f.append(
            f"[1:v]trim=start={s}:duration={seg:.4f},setpts=PTS-STARTPTS,"
            f"scale=w='trunc(1080*({z})/2)*2':h='trunc(1920*({z})/2)*2':eval=frame,crop=1080:1920{flash}[v{i}]")
        f.append(
            f"[1:a]atrim=start={s}:duration={seg:.4f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d=0.02,afade=t=out:st={seg-0.03:.4f}:d=0.03[a{i}]")
        cat += f"[v{i}][a{i}]"
    f.append(f"{cat}concat=n={n}:v=1:a=1[mc][ma]")

    tag = "This is the therapy I need."
    q0 = main_len - 5.0
    f.append(
        "[mc]curves=master='0/0 0.25/0.21 0.75/0.78 0.92/0.88 1/0.93',"
        "colorbalance=rs=-0.04:bs=0.05:rh=0.05:bh=-0.04,eq=contrast=1.1:saturation=1.2,"
        f"drawbox=x=0:y=ih*0.10:w=iw:h=170:color=black@0.42:t=fill:enable='between(t,0.2,4.0)',"
        f"drawtext=fontfile={SERIF_I}:text='{tag}':fontcolor=white:fontsize=78:shadowcolor=black@0.7:shadowx=3:shadowy=3:"
        f"x=(w-tw)/2:y=h*0.10+45:alpha='min(1,max(0,(t-0.2)/0.4))*min(1,max(0,(4.0-t)/0.5))',"
        f"drawbox=x=0:y=ih*0.08:w=iw:h=400:color=black@0.42:t=fill:enable='between(t,{q0:.2f},{main_len:.2f})',"
        + ",".join(
            f"drawtext=fontfile={SERIF_B}:text='{ln}':fontcolor=white:fontsize=96:shadowcolor=black@0.7:shadowx=3:shadowy=3:"
            f"x=(w-tw)/2:y=h*0.08+40+{i*115}:alpha='min(1,max(0,(t-{q0 + i*0.47:.2f})/0.3))*min(1,max(0,({main_len:.2f}-t)/0.4))'"
            for i, ln in enumerate(a.quote.split(". ")) for ln in [ln if ln.endswith(".") else ln + "."]) + ","
        "vignette=PI/6,fps=30,settb=1/30,format=yuv420p[vm]")
    f.append(f"[vi][vm]xfade=transition=circleopen:duration={xf}:offset={off},format=yuv420p[v]")
    f.append(f"[2:a]aresample=48000,atrim=0:{intro_len}[ai]")
    f.append(f"[ma]aresample=48000,volume={a.road_volume},afade=t=out:st={main_len-1.5:.2f}:d=1.5,"
             f"adelay={int(off*1000)}:all=1[am]")
    f.append("[ai][am]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.95[a]")

    total = off + main_len
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", os.path.join(HERE, "intro.mp4"), "-i", a.prep, "-i", a.intro_audio,
                    "-filter_complex", ";".join(f), "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-profile:v", "high",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out], check=True)
    print(f"Done -> {a.out}  ({total:.1f}s; footage/music drop at {off:.1f}s)")


if __name__ == "__main__":
    main()
