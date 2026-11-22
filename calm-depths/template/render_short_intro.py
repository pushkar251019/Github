#!/usr/bin/env python3
"""Calm Depths: short intro (12 s, 1920x1080, 30 fps). Replaces the 45 s intro for ambience videos.
Logo reveal, one short narrated line with captions, then the Subscribe moment.

  python3 template/render_short_intro.py --bg work/winter/main.mkv --amb work/winter/main_audio.wav \
      --out exports/CalmDepths_Intro_winter.mp4
"""
import argparse, json, math, os, subprocess, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brand as B
from render_intro import fade, ease, with_alpha, caption_image, gradient_layers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS, DUR = 1920, 1080, 30, 12.0
VO_START = 1.6
VDIR = os.path.join(ROOT, "assets", "voice_v2")
# (first word index, last word index, runs) on assets/voice_v2/words.json
CAPTIONS = [
    (0, 3, [("Welcome to ", False), ("Calm Depths.", True)]),
    (4, 8, [("Settle in by the fire,", False)]),
    (9, 14, [("and let the season ", False), ("slow down.", True)]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", required=True); ap.add_argument("--amb", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--scrim", type=int, default=150)
    ap.add_argument("--dim", type=int, default=40)
    ap.add_argument("--voice-dir", default=VDIR, help="folder with CalmDepths_Narrator_Short_v2.wav, words.json, optional captions.json")
    a = ap.parse_args()
    vdir = a.voice_dir
    words = json.load(open(os.path.join(vdir, "words.json")))
    cfile = os.path.join(vdir, "captions.json")
    lines = json.load(open(cfile)) if os.path.exists(cfile) else CAPTIONS
    caps = []
    for i0, i1, runs in lines:
        caps.append([words[i0][1] + VO_START - 0.12, words[i1][2] + VO_START + 0.35, caption_image(runs)])
    for k in range(len(caps) - 1):
        caps[k][1] = min(caps[k][1] + 0.25, caps[k + 1][0] - 0.04)
    vo_end = words[-1][2] + VO_START

    grad_bottom, grad_center = gradient_layers(a.scrim)
    dim = Image.new("RGBA", (W, H), B.CHARCOAL + (a.dim,))
    emb = B.emblem(170); desc = B.descriptor(24); tag = B.tagline(26)
    yt = B.yt_play(50); sub = B.subscribe_button("subscribe", 60); subd = B.subscribe_button("subscribed", 60)
    bell = B.bell(42)

    vo = os.path.join(vdir, "CalmDepths_Narrator_Short_v2.wav")
    fc = (f"[2:a]aresample=48000,adelay={int(VO_START*1000)}|{int(VO_START*1000)},apad,atrim=0:{DUR},asplit[vo][sc];"
          f"[1:a]aresample=48000,atrim=0:{DUR},volume=0.85[ambv];"
          f"[ambv][sc]sidechaincompress=threshold=0.03:ratio=3:attack=60:release=700[ambd];"
          f"[vo][ambd]amix=inputs=2:normalize=0:duration=first,afade=t=in:d=0.8,alimiter=limit=0.89[a];"
          f"[0:v]trim=0:{DUR},setpts=PTS-STARTPTS,fade=t=in:d=0.8[bg];"
          f"[bg][3:v]overlay=0:0:format=auto,format=yuv420p[v]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", a.bg, "-i", a.amb, "-i", vo,
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", str(DUR),
           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", a.out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    sub_in = vo_end + 0.5; press = sub_in + 1.2
    for fi in range(int(DUR * FPS)):
        t = fi / FPS
        fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        kc = fade(t, 0.3, 1.4, DUR - 1.6, DUR - 0.2)
        if kc:
            fr.alpha_composite(with_alpha(grad_center, kc)); fr.alpha_composite(with_alpha(dim, kc))
        kb = fade(t, 1.0, 2.0, vo_end + 0.4, vo_end + 1.2)
        if kb: fr.alpha_composite(with_alpha(grad_bottom, kb))
        # logo
        ko = fade(t, 0.4, 1.8, DUR - 1.6, DUR - 0.3); rise = (1 - ease((t - 0.4) / 1.6)) * 22
        if ko:
            fr.alpha_composite(with_alpha(emb, ko), ((W - emb.width) // 2, int(215 + rise)))
            wmk = with_alpha(B.wordmark(88, 0.44 - 0.14 * ease((t - 0.8) / 2.2)), fade(t, 0.9, 2.3, DUR - 1.6, DUR - 0.3))
            fr.alpha_composite(wmk, ((W - wmk.width) // 2, 405))
            kd = fade(t, 2.0, 3.0, DUR - 1.6, DUR - 0.3)
            if kd:
                fr.alpha_composite(with_alpha(desc, kd), ((W - desc.width) // 2, 535))
                L = int(110 * ease((t - 2.0) / 1.2)); ln = with_alpha(B.hairline(max(L, 1)), kd)
                fr.alpha_composite(ln, ((W - desc.width) // 2 - 30 - L, 535 + desc.height // 2))
                fr.alpha_composite(ln, ((W + desc.width) // 2 + 30, 535 + desc.height // 2))
            kt = fade(t, 3.2, 4.4, DUR - 1.6, DUR - 0.3)
            if kt: fr.alpha_composite(with_alpha(tag, kt), ((W - tag.width) // 2, 590))
        # captions
        for s, e_, img in caps:
            if s - 0.01 <= t <= e_:
                k = fade(t, s, s + 0.28, e_ - 0.24, e_)
                y = 930 - img.height // 2 + int((1 - ease((t - s) / 0.4)) * 8)
                fr.alpha_composite(with_alpha(img, k), ((W - img.width) // 2, y))
        # subscribe moment
        ks = fade(t, sub_in, sub_in + 0.6, DUR - 1.2, DUR - 0.3)
        if ks:
            btn = sub if t < press + 0.12 else subd
            sc = 1.0 - 0.06 * math.sin(math.pi * min(max((t - press) / 0.24, 0), 1))
            b2 = btn.resize((max(1, int(btn.width * sc)), max(1, int(btn.height * sc))), Image.LANCZOS)
            y0 = 700 + int((1 - ease((t - sub_in) / 0.6)) * 24)
            total = yt.width + 24 + sub.width + 24 + bell.width; x0 = (W - total) // 2
            fr.alpha_composite(with_alpha(yt, ks), (x0, y0 + (sub.height - yt.height) // 2))
            fr.alpha_composite(with_alpha(b2, ks), (x0 + yt.width + 24 + (sub.width - b2.width) // 2, y0 + (sub.height - b2.height) // 2))
            rt = t - (press + 0.5); ang = 14 * math.sin(rt * 18) * math.exp(-rt * 3) if rt > 0 else 0
            bl = bell.rotate(ang, resample=Image.BICUBIC, center=(bell.width / 2, bell.height * 0.2))
            fr.alpha_composite(with_alpha(bl, ks), (x0 + yt.width + 24 + sub.width + 24, y0 + (sub.height - bell.height) // 2))
        p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait()
    if p.returncode: sys.exit("ffmpeg failed")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
