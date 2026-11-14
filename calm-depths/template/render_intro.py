#!/usr/bin/env python3
"""Calm Depths — master intro renderer (45 s, 1920x1080, 30 fps).
Locked: narrator, script, captions, branding, subscribe, timing, mix.
Variable: background plate + ambience (built per theme).

  python3 template/render_intro.py --theme ocean
"""
import argparse, json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brand as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS, DUR = 1920, 1080, 30, 45.0
VO_START = 2.2                       # narration offset inside the intro

# Caption chunks: (word count, [(text, gold?) runs]) — mapped onto Whisper word timings.
CAPTIONS = [
    (6, [("Welcome, beautiful people,", True), (" to Calm Depths.", False)]),
    (5, [("We’re so glad you’re here.", False)]),
    (5, [("For the next little while,", False)]),
    (8, [("let the sounds around you carry you away", False)]),
    (6, [("from the noise of everyday life.", False)]),
    (5, [("Let your mind slow down,", True)]),
    (7, [("your body relax, and your thoughts settle.", False)]),
    (7, [("Whether you’re here to rest, focus, meditate,", False)]),
    (4, [("or simply feel refreshed,", False)]),
    (4, [("give yourself this moment.", True)]),
    (6, [("Take a slow, deep breath", True), (" in…", False)]),
    (4, [("and gently breathe out.", False)]),
    (5, [("Let go of the day,", False)]),
    (6, [("make room for a little peace,", False)]),
    (6, [("and allow yourself to simply be.", False)]),
    (6, [("Get comfortable, and enjoy the sounds.", False)]),
]


def ease(x):  # smooth in-out
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)


def fade(t, a, b, c, d):
    """0 before a, ramps to 1 by b, holds, ramps to 0 from c to d."""
    if t < a or t > d: return 0.0
    if t < b: return ease((t - a) / (b - a))
    if t > c: return 1 - ease((t - c) / (d - c))
    return 1.0


def with_alpha(img, k):
    if k >= 0.999: return img
    out = img.copy(); a = np.asarray(out.getchannel("A"), dtype=np.float32) * k
    out.putalpha(Image.fromarray(a.astype(np.uint8))); return out


def caption_image(runs, size=46):
    f_reg = B.sans(size, 450); f_gold = B.sans(size, 560)
    widths = [(f_gold if g else f_reg).getlength(t) for t, g in runs]
    asc, desc = f_reg.getmetrics()
    img = Image.new("RGBA", (int(sum(widths)) + 12, asc + desc + 12), (0, 0, 0, 0)); d = ImageDraw.Draw(img); x = 6
    for (t, g), w in zip(runs, widths):
        d.text((x, 6), t, font=f_gold if g else f_reg, fill=(B.GOLD if g else B.CREAM) + (255,)); x += w
    return B.add_shadow(img, radius=7, alpha=0.75)


def build_caption_track(words):
    track, i = [], 0
    for n, runs in CAPTIONS:
        ws = words[i:i + n]; i += n
        track.append([ws[0][1] + VO_START - 0.12, ws[-1][2] + VO_START + 0.30, caption_image(runs)])
    for k in range(len(track) - 1):          # never overlap the next line
        track[k][1] = min(track[k][1] + 0.25, track[k + 1][0] - 0.04)
    assert i == len(words), f"caption word count {i} != transcript {len(words)}"
    return track


def gradient_layers(scrim=140):
    y = np.linspace(0, 1, H)[:, None]
    bottom = np.clip((y - 0.62) / 0.38, 0, 1) ** 1.6 * 150         # caption legibility
    xx, yy = np.meshgrid(np.linspace(-1, 1, W), np.linspace(-1, 1, H))
    center = np.clip(1 - np.sqrt((xx / 0.9) ** 2 + (yy / 0.75) ** 2), 0, 1) ** 1.2 * scrim  # logo legibility
    def lay(a):
        arr = np.zeros((H, W, 4), np.uint8); arr[..., :3] = B.CHARCOAL
        arr[..., 3] = np.broadcast_to(a, (H, W)).astype(np.uint8); return Image.fromarray(arr, "RGBA")
    return lay(bottom), lay(center)


def breath_ring(r, alpha):
    s = int(r * 2 + 40); img = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for k, (dr, op) in enumerate([(0, 1.0), (10, 0.35), (22, 0.15)]):
        rr = r + dr; d.ellipse([s / 2 - rr, s / 2 - rr, s / 2 + rr, s / 2 + rr],
                               outline=B.GOLD + (int(255 * alpha * op),), width=3 if k == 0 else 2)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--theme", default="ocean")
    ap.add_argument("--out", default=None); a = ap.parse_args()
    work = os.path.join(ROOT, "work", a.theme)
    words = json.load(open(os.path.join(ROOT, "assets", "voice", "words.json")))
    segs = json.load(open(os.path.join(ROOT, "assets", "voice", "segments.json")))
    caps = build_caption_track(words)
    vo_end = segs[-1][1] + VO_START
    breath_in = (segs[4][0] + VO_START, segs[5][0] + VO_START)     # "Take a slow, deep breath in…" + pause
    breath_out = (segs[5][0] + VO_START, segs[5][1] + VO_START + 0.9)

    theme = json.load(open(os.path.join(ROOT, "template", "themes", a.theme + ".json")))
    grad_bottom, grad_center = gradient_layers(theme.get("logo_scrim", 140))
    dim = Image.new("RGBA", (W, H), B.CHARCOAL + (int(theme.get("logo_dim", 0)),))
    # static brand pieces
    emb = B.emblem(190); desc = B.descriptor(24)
    tag = B.tagline(28); wm = with_alpha(B.watermark(40), 0.72)
    stamp_emb = B.emblem(150); stamp_word = B.wordmark(84, 0.30); stamp_desc = B.descriptor(21)
    yt = B.yt_play(54); sub = B.subscribe_button("subscribe", 66); subd = B.subscribe_button("subscribed", 66)
    bell = B.bell(46)
    line = B.hairline(120)

    out = a.out or os.path.join(ROOT, "exports", f"CalmDepths_Intro_{a.theme}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    amb = os.path.join(work, "ambience.wav"); vo = os.path.join(ROOT, "assets", "voice", "CalmDepths_Narrator_Intro.wav")
    # --- audio mix: voice prominent, ambience ducked under narration, swelling after it ends
    amb_gain = (f"volume='if(lt(t,2),1.0*t/2,if(lt(t,{vo_end:.2f}),1.0-0.5*min(1,(t-2)/1.2),"
                f"0.5+0.95*min(1,(t-{vo_end:.2f})/2.4)))':eval=frame")
    fc = (f"[2:a]aresample=48000,adelay={int(VO_START*1000)}|{int(VO_START*1000)},apad,atrim=0:{DUR},asplit[vo][sc];"
          f"[1:a]aresample=48000,{amb_gain}[ambv];"
          f"[ambv][sc]sidechaincompress=threshold=0.03:ratio=3:attack=60:release=700:makeup=1[ambd];"
          f"[vo][ambd]amix=inputs=2:normalize=0:duration=first,afade=t=out:st={DUR-0.6}:d=0.6,"
          f"alimiter=limit=0.89,aresample=48000[a];"
          f"[0:v][3:v]overlay=0:0:format=auto,format=yuv420p[v]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", os.path.join(work, "background.mp4"), "-i", amb, "-i", vo,
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", str(DUR),
           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-r", str(FPS), "-g", "60", "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
           "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    N = int(DUR * FPS)
    for fi in range(N):
        t = fi / FPS
        fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        # legibility gradients
        kb = fade(t, 1.5, 3.0, vo_end + 0.4, vo_end + 1.6)
        if kb: fr.alpha_composite(with_alpha(grad_bottom, kb))
        kc = max(fade(t, 0.4, 1.6, 6.4, 7.6), fade(t, vo_end - 0.6, vo_end + 0.6, 44.0, 44.9))
        if kc:
            fr.alpha_composite(with_alpha(grad_center, kc))
            if theme.get("logo_dim"): fr.alpha_composite(with_alpha(dim, kc))

        # ---- opening logo (0.6 – 7.6 s)
        if 0.5 < t < 7.8:
            ko = fade(t, 0.6, 2.0, 6.5, 7.6); rise = (1 - ease((t - 0.6) / 1.6)) * 24
            e = with_alpha(emb, ko); fr.alpha_composite(e, ((W - emb.width) // 2, int(250 + rise)))
            trk = 0.46 - 0.16 * ease((t - 1.0) / 2.4)                          # letters settle together
            wmk = with_alpha(B.wordmark(92, trk), fade(t, 1.1, 2.6, 6.5, 7.6))
            fr.alpha_composite(wmk, ((W - wmk.width) // 2, 455))
            kd = fade(t, 2.3, 3.4, 6.5, 7.6)
            if kd:
                fr.alpha_composite(with_alpha(desc, kd), ((W - desc.width) // 2, 590))
                L = int(120 * ease((t - 2.3) / 1.2)); ln = with_alpha(B.hairline(max(L, 1)), kd)
                fr.alpha_composite(ln, ((W - desc.width) // 2 - 30 - L, 590 + desc.height // 2))
                fr.alpha_composite(ln, ((W + desc.width) // 2 + 30, 590 + desc.height // 2))

        # ---- corner watermark (identical to the main-video watermark)
        kw = fade(t, 7.4, 8.6, vo_end - 1.0, vo_end)
        if kw: fr.alpha_composite(with_alpha(wm, kw), (W - wm.width - 48, H - wm.height - 40))

        # ---- breathing ring
        if breath_in[0] - 0.3 < t < breath_out[1] + 0.8:
            if t < breath_in[1]: r = 70 + 110 * ease((t - breath_in[0]) / (breath_in[1] - breath_in[0]))
            else: r = 180 - 110 * ease((t - breath_out[0]) / (breath_out[1] - breath_out[0]))
            kr = fade(t, breath_in[0] - 0.3, breath_in[0] + 0.6, breath_out[1] - 0.2, breath_out[1] + 0.8) * 0.85
            ring = breath_ring(r, kr); fr.alpha_composite(ring, ((W - ring.width) // 2, 430 - ring.height // 2))

        # ---- captions
        for s, e_, img in caps:
            if s - 0.01 <= t <= e_:
                k = fade(t, s, s + 0.28, e_ - 0.24, e_)
                y = 925 - img.height // 2 + int((1 - ease((t - s) / 0.4)) * 8)
                fr.alpha_composite(with_alpha(img, k), ((W - img.width) // 2, y))

        # ---- outro brand stamp + tagline + subscribe
        if t > vo_end - 0.4:
            ko = fade(t, vo_end - 0.3, vo_end + 1.1, 44.0, 44.9); rise = (1 - ease((t - vo_end + 0.3) / 1.4)) * 18
            fr.alpha_composite(with_alpha(stamp_emb, ko), ((W - stamp_emb.width) // 2, int(205 + rise)))
            fr.alpha_composite(with_alpha(stamp_word, ko), ((W - stamp_word.width) // 2, int(365 + rise)))
            fr.alpha_composite(with_alpha(stamp_desc, ko), ((W - stamp_desc.width) // 2, int(475 + rise)))
            kt = fade(t, vo_end + 0.6, vo_end + 1.8, 44.0, 44.9)
            fr.alpha_composite(with_alpha(tag, kt), ((W - tag.width) // 2, 540))
            # subscribe row: [YT play] [SUBSCRIBE → SUBSCRIBED] [bell]
            ks = fade(t, vo_end + 1.3, vo_end + 2.0, 44.1, 44.9)
            if ks:
                press = vo_end + 2.6
                btn = sub if t < press + 0.12 else subd
                sc = 1.0 - 0.06 * math.sin(math.pi * min(max((t - press) / 0.24, 0), 1))
                b2 = btn.resize((max(1, int(btn.width * sc)), max(1, int(btn.height * sc))), Image.LANCZOS)
                pop = 1 - ease((t - vo_end - 1.3) / 0.7)
                y0 = 690 + int(pop * 26)
                total = yt.width + 26 + sub.width + 26 + bell.width
                x0 = (W - total) // 2
                fr.alpha_composite(with_alpha(yt, ks), (x0, y0 + (sub.height - yt.height) // 2))
                bx = x0 + yt.width + 26 + (sub.width - b2.width) // 2
                fr.alpha_composite(with_alpha(b2, ks), (bx, y0 + (sub.height - b2.height) // 2))
                ring_t = t - (press + 0.5)
                ang = 14 * math.sin(ring_t * 18) * math.exp(-ring_t * 3) if ring_t > 0 else 0
                bl = bell.rotate(ang, resample=Image.BICUBIC, center=(bell.width / 2, bell.height * 0.2))
                fr.alpha_composite(with_alpha(bl, ks), (x0 + yt.width + 26 + sub.width + 26, y0 + (sub.height - bell.height) // 2))
        p.stdin.write(fr.tobytes())
        if fi % 150 == 0: print(f"frame {fi}/{N}", flush=True)
    p.stdin.close(); p.wait()
    if p.returncode: sys.exit("ffmpeg failed")
    print("wrote", out)


if __name__ == "__main__":
    main()
