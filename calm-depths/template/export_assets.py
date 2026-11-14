#!/usr/bin/env python3
"""Exports the permanent Calm Depths brand assets (transparent PNGs + subscribe animation)."""
import math, os, subprocess, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brand as B
from render_intro import ease, fade, with_alpha

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "brand")


def save(img, name):
    img.save(os.path.join(OUT, name)); print("wrote", name, img.size)


def subscribe_frame(t, W=760, H=150, dur=5.0):
    """5-second transparent subscribe animation: pop in, press, bell ring, fade."""
    fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    yt, sub, subd, bell = B.yt_play(54), B.subscribe_button("subscribe", 66), B.subscribe_button("subscribed", 66), B.bell(46)
    ks = fade(t, 0.0, 0.6, dur - 0.7, dur)
    if not ks: return fr
    press = 1.5
    btn = sub if t < press + 0.12 else subd
    sc = 1.0 - 0.06 * math.sin(math.pi * min(max((t - press) / 0.24, 0), 1))
    b2 = btn.resize((max(1, int(btn.width * sc)), max(1, int(btn.height * sc))), Image.LANCZOS)
    y0 = (H - sub.height) // 2 + int((1 - ease(t / 0.6)) * 22)
    total = yt.width + 26 + sub.width + 26 + bell.width; x0 = (W - total) // 2
    fr.alpha_composite(with_alpha(yt, ks), (x0, y0 + (sub.height - yt.height) // 2))
    fr.alpha_composite(with_alpha(b2, ks), (x0 + yt.width + 26 + (sub.width - b2.width) // 2, y0 + (sub.height - b2.height) // 2))
    rt = t - (press + 0.5); ang = 14 * math.sin(rt * 18) * math.exp(-rt * 3) if rt > 0 else 0
    bl = bell.rotate(ang, resample=Image.BICUBIC, center=(bell.width / 2, bell.height * 0.2))
    fr.alpha_composite(with_alpha(bl, ks), (x0 + yt.width + 26 + sub.width + 26, y0 + (sub.height - bell.height) // 2))
    return fr


def encode(frames_fn, n, size, out, args):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{size[0]}x{size[1]}",
                          "-r", "30", "-i", "-", *args, out], stdin=subprocess.PIPE)
    for i in range(n): p.stdin.write(frames_fn(i).tobytes())
    p.stdin.close(); p.wait(); print("wrote", os.path.basename(out))


def main():
    os.makedirs(OUT, exist_ok=True)
    save(B.full_logo(1.0), "CalmDepths_Logo_Full_transparent.png")
    save(B.stack([B.full_logo(1.0), B.tagline(30)], gap=30), "CalmDepths_Logo_Tagline_transparent.png")
    save(B.emblem(1024), "CalmDepths_Emblem_1024_transparent.png")
    save(B.brand_stamp(80), "CalmDepths_BrandStamp_YouTube_transparent.png")
    save(B.watermark(46), "CalmDepths_Watermark_transparent.png")
    save(B.watermark(92), "CalmDepths_Watermark_2x_transparent.png")
    save(B.subscribe_button("subscribe", 132), "CalmDepths_SubscribeButton_transparent.png")
    # channel profile picture (square, charcoal) – handy for YouTube
    pp = Image.new("RGBA", (800, 800), B.CHARCOAL + (255,)); e = B.emblem(560); pp.alpha_composite(e, (120, 120))
    save(pp.convert("RGB"), "CalmDepths_ProfilePicture_800.png")

    W, H, D = 760, 150, 5.0; n = int(D * 30)
    f = lambda i: subscribe_frame(i / 30, W, H, D)
    encode(f, n, (W, H), os.path.join(OUT, "CalmDepths_Subscribe_5s_alpha.mov"),
           ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-alpha_bits", "8"])
    encode(f, n, (W, H), os.path.join(OUT, "CalmDepths_Subscribe_5s_alpha.webm"),
           ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24", "-auto-alt-ref", "0"])
    # 60 s loop cycle (55 s empty + 5 s animation) used by brand_long_video.py
    blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = lambda i: blank if i < 55 * 30 else subscribe_frame((i - 55 * 30) / 30, W, H, D)
    encode(g, 60 * 30, (W, H), os.path.join(OUT, "CalmDepths_Subscribe_60s_cycle_alpha.mov"),
           ["-c:v", "qtrle", "-pix_fmt", "argb"])
    # preview on charcoal (for quick viewing)
    encode(lambda i: Image.alpha_composite(Image.new("RGBA", (W, H), B.CHARCOAL + (255,)), f(i)), n, (W, H),
           os.path.join(OUT, "CalmDepths_Subscribe_5s_preview.mp4"), ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16"])


if __name__ == "__main__":
    main()
