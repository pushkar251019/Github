"""Unseen Depth of Life branded Reel frame.

Places any video inside the window of the brand frame (brand/frame_source.png), adds the
@handle, a soft inner shadow, a flickering lantern and a breathing sun glow.

    python3 frame_template.py build                 # (re)build brand/frame_overlay.png + frame.json
    python3 frame_template.py compose in.mp4 out.mp4 # any video -> 1080x1920 framed Reel

Other scripts can import `window()` to render content at the exact window size.
"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = os.path.join(HERE, "brand")
SRC, OVERLAY, META = (os.path.join(BRAND, f) for f in ("frame_source.png", "frame_overlay.png", "frame.json"))
W, H, FPS = 1080, 1920, 30
HANDLE = "@unseen_depth_of_life"


def build():
    src = Image.open(SRC).convert("RGBA")
    k = W / src.width
    im = src.resize((W, H), Image.LANCZOS)
    a = np.asarray(im)[..., 3]
    ys, xs = np.nonzero(a < 128)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    # content box: even-sized, slightly larger than the window so the frame's alpha does the cropping
    x0, y0 = (x0 - 2) & ~1, (y0 - 2) & ~1
    cw, ch = ((x1 + 2 - x0) + 1) & ~1, ((y1 + 2 - y0) + 1) & ~1

    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(os.path.join(HERE, "fonts", "Inter-Medium.otf"), 27)
    rgb = np.asarray(src)[..., :3].astype(int)                 # centre the handle under the title rule
    rule = np.nonzero((rgb[100:140, 300:800].sum(-1) < 120).any(0))[0] + 300
    cx = (rule.min() + rule.max()) / 2 * k if len(rule) else W / 2
    text = " ".join(HANDLE)                                    # letter-spaced, matches the title style
    tw = d.textlength(text, font=font)
    d.text((cx - tw / 2, 168), text, font=font, fill=(74, 44, 12, 235))
    im.save(OVERLAY)
    meta = dict(x=int(x0), y=int(y0), w=int(cw), h=int(ch),
                lantern=[round(90 * k), round(186 * k)], sun=[round(673 * k), round(1421 * k)])
    json.dump(meta, open(META, "w"), indent=1)
    return meta


def window():
    return json.load(open(META)) if os.path.exists(META) else build()


def _glow(h, w, cx, cy, radius):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * radius ** 2))


def compose(inp, out):
    m = window()
    ov = np.asarray(Image.open(OVERLAY).convert("RGBA")).astype(np.float32) / 255
    X, Y, CW, CH = m["x"], m["y"], m["w"], m["h"]
    a_win = ov[Y:Y + CH, X:X + CW, 3:4]
    rgb_win = ov[Y:Y + CH, X:X + CW, :3]
    # inner shadow: content darkens toward the window edge -> sense of depth
    transp = (a_win[..., 0] < 0.5).astype(np.float32)
    blur = np.asarray(Image.fromarray((transp * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(22)), np.float32) / 255
    shade = (0.55 + 0.45 * blur)[..., None]
    base = (ov[..., :3] * 255).astype(np.float32)
    # animated light patches (outside the window, additive)
    lx, ly = m["lantern"]; sx, sy = m["sun"]
    L = 150; lant = _glow(2 * L, 2 * L, L, L, 46)[..., None] * np.array([255, 190, 90], np.float32)
    S = 220; sun = _glow(2 * S, 2 * S, S, S, 70)[..., None] * np.array([255, 205, 120], np.float32)

    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", inp],
                           capture_output=True, text=True).stdout.strip()
    dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", inp, "-vf",
        f"fps={FPS},scale={CW}:{CH}:force_original_aspect_ratio=increase:flags=lanczos,crop={CW}:{CH}",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", inp, "-map", "0:v", "-map", "1:a?",
        "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", "-shortest", out], stdin=subprocess.PIPE)
    rng = np.random.default_rng(3); flick = 0.0; n = 0; size = CW * CH * 3
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size: break
        s = n / FPS; n += 1
        frame = base.copy()
        c = np.frombuffer(buf, np.uint8).reshape(CH, CW, 3).astype(np.float32) * shade
        frame[Y:Y + CH, X:X + CW] = c * (1 - a_win) + rgb_win * 255 * a_win
        flick = 0.85 * flick + 0.15 * rng.uniform(-1, 1)
        li = 0.30 + 0.06 * np.sin(s * 2.3) + 0.10 * flick
        frame[ly - L:ly + L, max(lx - L, 0):lx + L] += li * lant[:, L - min(lx, L):]
        si = 0.16 + 0.07 * np.sin(2 * np.pi * s / 7)
        y0, y1, x0, x1 = sy - S, min(sy + S, H), sx - S, min(sx + S, W)
        frame[y0:y1, x0:x1] += si * sun[:y1 - y0, :x1 - x0]
        enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait(); dec.wait()
    print(f"wrote {out} ({n} frames, source {probe}s)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build": print(build())
    elif cmd == "compose": compose(sys.argv[2], sys.argv[3])
    else: sys.exit(__doc__)
