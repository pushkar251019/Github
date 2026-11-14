"""Calm Depths — brand kit (single source of truth for colours, fonts and marks).
Every intro, watermark and subscribe asset is drawn from these functions, so the
identity stays identical across all videos."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "assets", "fonts")

CHARCOAL = (18, 18, 20)
GOLD = (200, 168, 108)
CREAM = (244, 236, 222)
YT_RED = (255, 0, 0)

NAME = "CALM DEPTHS"
DESCRIPTOR = "SOUNDS • MINDFULNESS • INNER CALM"
TAGLINE = "ESCAPE THE NOISE. FIND YOUR CALM."


def serif(size, weight=500, italic=False):
    f = ImageFont.truetype(os.path.join(FONTS, "CormorantGaramond-Italic-Variable.ttf" if italic
                                        else "CormorantGaramond-Variable.ttf"), size)
    f.set_variation_by_axes([weight]); return f


def sans(size, weight=500):
    f = ImageFont.truetype(os.path.join(FONTS, "Montserrat-Variable.ttf"), size)
    f.set_variation_by_axes([weight]); return f


def tracked(text, font, tracking, fill, shadow=True):
    """Render letter-spaced text to a tight RGBA image. tracking is in em."""
    sp = font.size * tracking
    widths = [font.getlength(c) for c in text]
    w = int(sum(widths) + sp * (len(text) - 1)) + 8
    asc, desc = font.getmetrics(); h = asc + desc + 8
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img); x = 4
    for c, cw in zip(text, widths):
        d.text((x, 4), c, font=font, fill=fill); x += cw + sp
    return add_shadow(img) if shadow else img


def add_shadow(img, radius=None, alpha=0.55):
    radius = radius or max(2, img.height // 14)
    pad = radius * 3
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, CHARCOAL + (0,))
    a = Image.new("L", out.size, 0); a.paste(img.getchannel("A"), (pad, pad))
    a = a.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * alpha))
    sh.putalpha(a); out = Image.alpha_composite(out, sh)
    out.alpha_composite(img, (pad, pad - 1)); return out


def emblem(size=400, color=GOLD):
    """Gold ring holding three receding waves — 'calm on the surface, depth beneath'."""
    S = size * 4; img = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    lw = max(4, S // 70); m = lw * 2
    d.ellipse([m, m, S - m, S - m], outline=color + (255,), width=lw)
    import math
    for i, (yy, a, op) in enumerate([(0.44, 0.055, 255), (0.56, 0.045, 190), (0.68, 0.035, 120)]):
        inset = 0.20 + i * 0.07
        pts = []
        for k in range(200):
            x = S * inset + (S * (1 - 2 * inset)) * k / 199
            y = S * yy + S * a * math.sin(2 * math.pi * (k / 199) * 1.5 + 0.6)
            pts.append((x, y))
        d.line(pts, fill=color + (op,), width=lw, joint="curve")
    # small moon / sun mark
    r = S * 0.045; cx, cy = S * 0.5, S * 0.27
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CREAM + (235,))
    return img.resize((size, size), Image.LANCZOS)


def wordmark(height=120, tracking=0.32, color=CREAM, weight=500):
    return tracked(NAME, serif(height, weight), tracking, color)


def descriptor(size=26, color=GOLD):
    return tracked(DESCRIPTOR, sans(size, 500), 0.28, color)


def tagline(size=30, color=GOLD):
    return tracked(TAGLINE, sans(size, 500), 0.24, color)


def yt_play(h=60):
    """Generic red play-button mark (YouTube-style) used next to the brand stamp."""
    S = 4; w = int(h * 1.42); img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=int(h * S * 0.28), fill=YT_RED + (255,))
    cx, cy, tr = w * S * 0.52, h * S * 0.5, h * S * 0.22
    d.polygon([(cx - tr * 0.8, cy - tr), (cx - tr * 0.8, cy + tr), (cx + tr * 1.05, cy)], fill=(255, 255, 255, 255))
    return img.resize((w, h), Image.LANCZOS)


def stack(items, gap=20, align="center"):
    w = max(i.width for i in items); h = sum(i.height for i in items) + gap * (len(items) - 1)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0)); y = 0
    for i in items:
        x = (w - i.width) // 2 if align == "center" else 0
        out.alpha_composite(i, (x, y)); y += i.height + gap
    return out


def row(items, gap=20):
    h = max(i.height for i in items); w = sum(i.width for i in items) + gap * (len(items) - 1)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0)); x = 0
    for i in items:
        out.alpha_composite(i, (x, (h - i.height) // 2)); x += i.width + gap
    return out


def hairline(w, color=GOLD, alpha=200):
    img = Image.new("RGBA", (w, 2), color + (alpha,)); return img


def full_logo(scale=1.0):
    e = emblem(int(220 * scale)); wm = wordmark(int(118 * scale)); ds = descriptor(int(25 * scale))
    return stack([e, wm, ds], gap=int(10 * scale))


def brand_stamp(h=56):
    """YouTube play mark + CALM DEPTHS stamp (horizontal)."""
    return row([yt_play(h), emblem(int(h * 1.15)), tracked(NAME, serif(int(h * 0.8), 600), 0.22, CREAM)], gap=int(h * 0.3))


def watermark(h=46):
    return row([emblem(h), tracked(NAME, serif(int(h * 0.62), 600), 0.22, CREAM, shadow=True)], gap=int(h * 0.25))


def subscribe_button(state="subscribe", h=78):
    """Red pill SUBSCRIBE button; state 'subscribed' gives the grey confirmed look."""
    S = 3; f = sans(int(h * 0.36 * S), 650)
    label = "SUBSCRIBE" if state == "subscribe" else "SUBSCRIBED  ✓"
    if state != "subscribe":
        f = sans(int(h * 0.36 * S), 650)
        label = "SUBSCRIBED"
    tw = f.getlength(label); tracking = h * S * 0.03
    tw += tracking * (len(label) - 1)
    pad = h * S * 0.62; extra = h * S * 0.5 if state != "subscribe" else 0
    w = int(tw + pad * 2 + extra); H = h * S
    img = Image.new("RGBA", (w, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    fill = (204, 0, 0, 255) if state == "subscribe" else (62, 62, 66, 240)
    d.rounded_rectangle([0, 0, w - 1, H - 1], radius=H // 2, fill=fill)
    x = pad; asc, desc = f.getmetrics(); y = (H - (asc + desc)) / 2 + H * 0.02
    if state != "subscribe":   # check mark
        cx, cy, s = pad * 0.95, H / 2, H * 0.14
        d.line([(cx - s, cy), (cx - s * 0.25, cy + s * 0.8), (cx + s * 1.2, cy - s * 0.9)], fill=CREAM + (255,), width=max(3, H // 22), joint="curve")
        x += extra * 0.7
    for c in label:
        d.text((x, y), c, font=f, fill=(255, 255, 255, 255)); x += f.getlength(c) + tracking
    return add_shadow(img.resize((w // S, h), Image.LANCZOS), alpha=0.45)


def bell(h=60, color=CREAM):
    S = 4; img = Image.new("RGBA", (h * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(img); H = h * S
    d.pieslice([H * 0.22, H * 0.12, H * 0.78, H * 0.75], 180, 360, fill=color + (255,))
    d.rectangle([H * 0.22, H * 0.43, H * 0.78, H * 0.68], fill=color + (255,))
    d.rounded_rectangle([H * 0.14, H * 0.64, H * 0.86, H * 0.74], radius=H * 0.04, fill=color + (255,))
    d.ellipse([H * 0.43, H * 0.74, H * 0.57, H * 0.86], fill=color + (255,))
    d.ellipse([H * 0.46, H * 0.06, H * 0.54, H * 0.14], fill=color + (255,))
    return add_shadow(img.resize((h, h), Image.LANCZOS), alpha=0.45)
