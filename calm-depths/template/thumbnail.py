#!/usr/bin/env python3
"""Calm Depths — thumbnail builder (1280x720) in the channel's established style.
  thumbnail.py <background.jpg> <out.jpg> --topic "RAIN SOUNDS FOR" --length "30 MINUTES" [--keep-title]
--keep-title only adds the brand header (emblem + descriptor) to an image that already carries the title."""
import argparse, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brand as B

W, H = 1280, 720


def gold_text(text, font):
    asc, desc = font.getmetrics(); w = int(font.getlength(text)) + 20; h = asc + desc + 20
    mask = Image.new("L", (w, h), 0); ImageDraw.Draw(mask).text((10, 10), text, font=font, fill=255)
    y = np.linspace(0, 1, h)[:, None]  # (h,1)
    top, mid, bot = np.array([255, 236, 190]), np.array([232, 192, 120]), np.array([196, 146, 72])
    g = np.where(y < 0.5, top + (mid - top) * (y / 0.5), mid + (bot - mid) * ((y - 0.5) / 0.5))  # (h,3)
    rgb = np.ascontiguousarray(np.broadcast_to(g.reshape(h, -1, 3)[:, :1, :], (h, w, 3))).astype(np.uint8)
    img = Image.fromarray(rgb, "RGB").convert("RGBA"); img.putalpha(mask)
    return B.add_shadow(img, radius=10, alpha=0.7)


def scrim(img, top=0.0, bottom=0.62, strength=150):
    y = np.linspace(0, 1, H)[:, None]
    a = np.clip(1 - np.abs(y - (top + bottom) / 2) / ((bottom - top) / 2), 0, 1) ** 1.3 * strength
    xx = np.linspace(-1, 1, W)[None, :]; a = a * np.clip(1.25 - np.abs(xx) * 0.6, 0, 1)
    lay = np.zeros((H, W, 4), np.uint8); lay[..., :3] = B.CHARCOAL; lay[..., 3] = a.astype(np.uint8)
    return Image.alpha_composite(img, Image.fromarray(lay, "RGBA"))


def header(img, y=18):
    e = B.emblem(56); d = B.descriptor(17)
    img.alpha_composite(d, ((W - d.width) // 2, y))
    L = 120; ln = B.hairline(L, alpha=210); cy = y + d.height // 2
    img.alpha_composite(ln, ((W - d.width) // 2 - 16 - L, cy)); img.alpha_composite(ln, ((W + d.width) // 2 + 16, cy))
    img.alpha_composite(B.add_shadow(e, alpha=0.5), ((W - e.width) // 2 - 8, y + d.height - 14))
    return img


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("bg"); ap.add_argument("out")
    ap.add_argument("--topic", default=""); ap.add_argument("--uses", default="FOCUS • RELAXATION • SLEEP • MEDITATION")
    ap.add_argument("--length", default="30 MINUTES"); ap.add_argument("--keep-title", action="store_true")
    a = ap.parse_args()
    img = Image.open(a.bg).convert("RGBA")
    r = max(W / img.width, H / img.height); img = img.resize((int(img.width * r + .5), int(img.height * r + .5)), Image.LANCZOS)
    img = img.crop(((img.width - W) // 2, (img.height - H) // 2, (img.width - W) // 2 + W, (img.height - H) // 2 + H))
    if not a.keep_title:
        img = scrim(img)
        t = gold_text("Calm Depths", B.serif(150, 600)); img.alpha_composite(t, ((W - t.width) // 2, 112))
        tp = B.tracked(a.topic, B.sans(30, 500), 0.16, B.CREAM); img.alpha_composite(tp, ((W - tp.width) // 2, 312))
        us = B.tracked(a.uses, B.sans(22, 500), 0.16, B.CREAM); img.alpha_composite(us, ((W - us.width) // 2, 360))
        f = B.sans(26, 700); tw = f.getlength(a.length) + 0.12 * 26 * (len(a.length) - 1)
        pill = Image.new("RGBA", (int(tw + 64), 54), (0, 0, 0, 0)); d = ImageDraw.Draw(pill)
        d.rounded_rectangle([0, 0, pill.width - 1, 53], radius=10, fill=(236, 196, 120, 245))
        txt = B.tracked(a.length, f, 0.12, B.CHARCOAL, shadow=False)
        pill.alpha_composite(txt, ((pill.width - txt.width) // 2, (54 - txt.height) // 2))
        img.alpha_composite(B.add_shadow(pill, alpha=0.5), ((W - pill.width) // 2 - 8, 408))
    img = header(img)
    img.convert("RGB").save(a.out, quality=93); print("wrote", a.out)


if __name__ == "__main__":
    main()
