"""Unseen Depth of Life — 10 quote Reels in the brand frame.

Each Reel: question hook -> quote revealed word by word (2-3 saffron key words) -> an original
Unseen Depth line -> save CTA, over an animated lamp-card scene, then framed by frame_template.
Quotes were transcribed from the source compilation video; the footage itself is not reused.

    python3 make_quotes.py            # all 10
    python3 make_quotes.py 3 7        # only reels 3 and 7
"""
import os, subprocess, sys, wave
import numpy as np
from frame_template import window, compose

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, ".build", "quotes"); OUTDIR = os.path.join(HERE, "quotes")
os.makedirs(TMP, exist_ok=True); os.makedirs(OUTDIR, exist_ok=True)
_fdir = os.path.expanduser("~/.fonts")                            # libass resolves the serif via fontconfig
if not os.path.exists(os.path.join(_fdir, "CormorantGaramond.ttf")):
    os.makedirs(_fdir, exist_ok=True)
    subprocess.run(f"cp {HERE}/fonts/* {_fdir}/ && fc-cache -f", shell=True, check=True)
_win = window(); W, H = _win["w"], _win["h"]; VW, VH = W // 2, H // 2
FPS, SR = 30, 44100

# (series label, hook, quote, saffron words, author or "", original line, palette, drone root Hz)
REELS = [
    ("CALM MIND · 01", "Where does real strength live?", "You are at your strongest when you are calm.",
     {"strongest", "calm."}, "", "Storms shout. The ocean's depth stays silent.", "saffron", 110.0),
    ("CALM MIND · 02", "Why do answers come when you stop chasing them?", "The calmer you are, the clearer you think.",
     {"calmer", "clearer"}, "", "Let the water settle. The moon appears on its own.", "indigo", 98.0),
    ("INNER STRENGTH · 03", "Who is in charge — you, or your mood?", "Train your mind to be stronger than your feelings.",
     {"mind", "stronger"}, "", "Feelings are guests. Don't hand them the keys.", "rose", 103.8),
    ("CLEAR CHOICES · 04", "Upset right now? Read this first.", "Never make a permanent decision based on temporary feelings.",
     {"permanent", "temporary"}, "", "Let the storm pass. Then choose.", "ember", 116.5),
    ("INNER STRENGTH · 05", "What is your pain trying to teach you?", "Turn your wounds into wisdom.",
     {"wounds", "wisdom."}, "", "Every scar is a lesson you never need to repeat.", "saffron", 87.3),
    ("CALM MIND · 06", "How much of what you fear has actually happened?", "We suffer more in imagination than in reality.",
     {"imagination", "reality."}, "Seneca", "Come back to this breath. It is the only place you live.", "indigo", 92.5),
    ("INNER STRENGTH · 07", "Who are you still trying to impress?", "Focus on improving yourself, not proving yourself.",
     {"improving", "proving"}, "", "The lamp doesn't argue with the dark. It simply burns.", "ember", 110.0),
    ("INNER STRENGTH · 08", "Feel like you're not moving forward?",
     "A river cuts through rock not because of its power, but because of its persistence.",
     {"persistence."}, "", "Small steps, every day. That is how mountains move.", "rose", 98.0),
    ("CLEAR CHOICES · 09", "Can't stop replaying what happened?", "Accept what is, let go of what was, have faith in what will be.",
     {"Accept", "go", "faith"}, "", "Hold the present gently. Release the past fully.", "saffron", 103.8),
    ("CLEAR CHOICES · 10", "Is life falling apart — or falling into place?",
     "Not all storms come to disrupt your life. Some come to clear your path.",
     {"clear", "path."}, "", "What leaves you was only making room.", "indigo", 87.3),
]
PALETTES = {  # background top, background bottom, lamp/halo colour, accent particles
    "saffron": ([.035, .022, .018], [.16, .07, .02], [1.0, .62, .22], [1.0, .78, .45]),
    "ember":   ([.040, .018, .014], [.18, .05, .02], [1.0, .45, .18], [1.0, .62, .35]),
    "rose":    ([.040, .020, .030], [.15, .05, .07], [1.0, .55, .45], [1.0, .75, .65]),
    "indigo":  ([.020, .020, .050], [.10, .06, .12], [1.0, .70, .35], [.85, .80, 1.0]),
}

def ts(s): s = max(0, s); return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"

def timeline(quote, orig):
    words = quote.split()
    q0 = 2.8; step = 0.24
    reveal_end = q0 + len(words) * step + 0.5
    orig_t = reveal_end + 0.6 + len(words) * 0.16          # time to read before the original line
    fade_t = orig_t + 1.4 + len(orig.split()) * 0.28
    cta_t = fade_t + 0.4
    return dict(q0=q0, step=step, orig=orig_t, fade=fade_t, cta=cta_t, dur=cta_t + 3.0)

def build_ass(i, label, hook, quote, keys, author, orig, T):
    big = 100 if len(quote) < 50 else 90 if len(quote) < 66 else 80
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Label,Inter Medium,26,&H0060C8FF,&H00FFFFFF,&H80100818,&H00000000,0,0,0,0,100,100,10,0,1,1,0,8,0,0,74,1
Style: Hook,Inter SemiBold,58,&H00FFFFFF,&H00FFFFFF,&H90100818,&H80000000,0,0,0,0,100,100,0,0,1,2,2,5,90,90,0,1
Style: Quote,Cormorant Garamond,{big},&H00FFFFFF,&H00FFFFFF,&H80100818,&H80000000,0,0,0,0,100,100,0,0,1,1.6,2,8,80,80,300,1
Style: Author,Inter Medium,28,&H00C8D8E8,&H00FFFFFF,&H80100818,&H00000000,0,0,0,0,100,100,6,0,1,1,0,8,0,0,640,1
Style: Orig,Cormorant Garamond,56,&H00E0ECF5,&H00FFFFFF,&H80100818,&H00000000,0,1,0,0,100,100,0,0,1,1.2,0,8,100,100,720,1
Style: Sign,Cormorant Garamond,44,&H0060C8FF,&H00FFFFFF,&H80100818,&H00000000,0,1,0,0,100,100,1,0,1,1,0,8,0,0,880,1
Style: CTA,Inter SemiBold,46,&H00FFFFFF,&H00FFFFFF,&H90100818,&H80000000,0,0,0,0,100,100,0,0,1,2,2,5,100,100,0,1
Style: CTA2,Inter Medium,30,&H0060C8FF,&H00FFFFFF,&H90100818,&H00000000,0,0,0,0,100,100,4,0,1,1,0,5,100,100,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""
    ev = []
    E = lambda a, b, st, tx: ev.append(f"Dialogue: 0,{ts(a)},{ts(b)},{st},,0,0,0,,{tx}")
    E(0.2, T["dur"] - 0.3, "Label", r"{\fad(500,400)}" + label)
    # hook: punches in (scale 92->100) and blurs out
    E(0.0, 2.6, "Hook", r"{\fad(250,350)\fscx92\fscy92\t(0,400,\fscx100\fscy100)\t(2100,2600,\blur6)}" + hook)
    # quote: each word fades + un-blurs in sequence, key words in saffron
    parts = []
    for k, w in enumerate(quote.split()):
        a = int(k * T["step"] * 1000); b = a + 520
        col = r"\c&H3AA8FF&" if w in keys else r"\c&HFFFFFF&"
        parts.append(f"{{{col}\\alpha&HFF&\\blur8\\t({a},{b},\\alpha&H00&\\blur0)}}{w}")
    E(T["q0"], T["fade"], "Quote", r"{\fad(0,500)}" + " ".join(parts))
    if author:
        E(T["orig"] - 0.8, T["fade"], "Author", r"{\fad(500,500)}— " + author.upper())
    E(T["orig"], T["fade"], "Orig", r"{\fad(600,500)\blur4\t(0,600,\blur0)}" + orig)
    E(T["orig"] + 0.5, T["fade"], "Sign", r"{\fad(600,500)}— Unseen Depth")
    E(T["cta"], T["dur"] - 0.4, "CTA", r"{\fad(400,400)\pos(%d,%d)}Save this for the day you need it." % (W // 2, H // 2 - 30))
    E(T["cta"] + 0.5, T["dur"] - 0.4, "CTA2", r"{\fad(400,400)\pos(%d,%d)}SEND IT TO SOMEONE WHO DOES" % (W // 2, H // 2 + 40))
    path = f"{TMP}/q{i:02d}.ass"; open(path, "w").write(hdr + "\n" + "\n".join(ev) + "\n"); return path

def build_audio(i, T, root, seed):
    dur = T["dur"]; N = int(dur * SR); t = np.arange(N) / SR; rng = np.random.default_rng(seed)
    drone = lambda off: sum(a * np.sin(2 * np.pi * (f + off) * t) for f, a in
                            [(root / 2, .20), (root, .30), (root * 1.5, .13), (root * 2, .07), (root * 3, .02)])
    swell = 0.7 + 0.3 * np.sin(2 * np.pi * t / 8 - np.pi / 2)
    n = np.cumsum(rng.standard_normal(N)); n -= np.convolve(n, np.ones(500) / 500, "same")
    air = n / np.abs(n).max() * 0.05
    def bowl(at, f0, g):
        out = np.zeros(N); j = int(at * SR); tt = t[:N - j]
        out[j:] = sum(a * np.sin(2 * np.pi * f * tt) * np.exp(-tt / d) for f, a, d in
                      [(f0, .5, 7), (f0 * 2.69, .3, 5), (f0 * 5.02, .15, 3), (f0 * 8.05, .06, 2)]) * g * (1 - np.exp(-tt * 80))
        return out
    hits = bowl(0.05, root * 2, .28) + bowl(T["q0"], root * 2, .34) + bowl(T["orig"], root * 3, .16) + bowl(T["cta"], root * 2, .18)
    chimes = np.zeros(N)
    for st in np.sort(rng.uniform(1.5, dur - 1.5, 6)):
        j = int(st * SR); m = min(int(3 * SR), N - j); tt = t[:m]; f = root * 4 * rng.choice([1, 9 / 8, 5 / 4, 3 / 2, 5 / 3])
        chimes[j:j + m] += np.sin(2 * np.pi * f * tt) * np.exp(-tt / 1.0) * .04 * (1 - np.exp(-tt * 200))
    fade = np.minimum(1, np.minimum(t / 0.3, (dur - t) / 0.8))
    L = (drone(0) * swell + air + chimes * .9 + hits) * fade; R = (drone(.5) * swell + air + chimes * 1.1 + hits) * fade
    st = np.stack([L, R], 1); st = st / np.abs(st).max() * .89
    path = f"{TMP}/q{i:02d}.wav"
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())
    return path

def render(i):
    label, hook, quote, keys, author, orig, pal, root = REELS[i - 1]
    T = timeline(quote, orig); ass = build_ass(i, label, hook, quote, keys, author, orig, T)
    wav = build_audio(i, T, root, i)
    top, bot, lamp, dust = (np.array(c, np.float32) for c in PALETTES[pal])
    rng = np.random.default_rng(100 + i)
    y, x = np.mgrid[0:VH, 0:VW].astype(np.float32); u, v = x / VW, y / VH
    bg = top * (1 - v[..., None]) + bot * v[..., None]
    lx, ly = 0.5, 0.86                                     # lamp near the bottom of the window
    dx, dy = (u - lx) * VW / VH, v - ly
    r = np.sqrt(dx ** 2 + dy ** 2); ang = np.arctan2(dx, -dy)
    vign = np.clip(1.3 - 1.1 * np.sqrt((u - .5) ** 2 + (v - .5) ** 2 * .8), .2, 1)[..., None]
    stars = ((rng.random((VH, VW)) > .9982) * rng.random((VH, VW))).astype(np.float32)
    NP = 55; px, py = rng.uniform(.3, .7, NP) * VW, rng.uniform(0, 1, NP) * VH
    pv = rng.uniform(10, 26, NP); pp = rng.uniform(0, 6.3, NP); pa = rng.uniform(.2, .6, NP)
    sg = np.exp(-(np.mgrid[-3:4, -3:4] ** 2).sum(0) / 2.5).astype(np.float32)
    content = f"{TMP}/q{i:02d}_content.mp4"
    vf = f"scale={W}:{H}:flags=lanczos,ass={ass}:fontsdir={HERE}/fonts,noise=alls=3:allf=t,format=yuv420p"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}",
        "-r", str(FPS), "-i", "-", "-i", wav, "-vf", vf, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest", content], stdin=subprocess.PIPE)
    flick = 0.0
    for fi in range(int(T["dur"] * FPS)):
        s = fi / FPS
        flick = .8 * flick + .2 * rng.uniform(-1, 1)
        g = 1 + .08 * np.sin(s * 3.1) + .10 * flick
        # loop-safe motion: everything periodic in the reel's duration
        ph = 2 * np.pi * s / T["dur"]
        halo = np.exp(-r / .26) * .55 * g + np.exp(-(r / .07) ** 2) * .4 * g
        sway = .003 * np.sin(s * 7) + .002 * flick
        fy = dy + .05; fw = .011 * np.clip(1 + fy / .035, .15, 1.6)          # teardrop: narrow tip, round base
        flame = np.exp(-(((dx - sway * (-fy / .04)) / fw) ** 2 + (fy / .032) ** 2)) * 1.3 * g
        core = np.exp(-((dx / .005) ** 2 + ((fy - .012) / .012) ** 2)) * .8
        rays = (.5 + .5 * np.cos(9 * ang + ph)) ** 10 * np.exp(-r / .55) * (dy < 0) * .06
        img = bg + (halo + rays)[..., None] * lamp + flame[..., None] * lamp * 1.1 + core[..., None]
        bowl = ((dx / .075) ** 2 + ((dy + .012) / .034) ** 2 < 1) & (dy > -.012)           # diya bowl
        rim = np.exp(-((dy + .012) / .004) ** 2) * (np.abs(dx) < .075)
        img = np.where(bowl[..., None], np.array([.16, .07, .03], np.float32) * ((1.6 - (dy + .012) / .034) * g)[..., None], img)
        img += (rim * .5 * g)[..., None] * lamp
        img += (stars * (.5 + .5 * np.sin(s * 1.4 + x * .03 + y * .02)))[..., None] * .6
        pyy = (py - pv * T["dur"] * 3 * (s / T["dur"])) % VH; pxx = px + 8 * np.sin(s * .7 + pp)
        dust_l = np.zeros((VH + 7, VW + 7), np.float32)
        for k in range(NP):
            iy, ix = int(pyy[k]), int(np.clip(pxx[k], 0, VW - 1))
            dust_l[iy:iy + 7, ix:ix + 7] += sg * pa[k] * (.6 + .4 * np.sin(s * 2 + pp[k])) * (pyy[k] / VH)
        img += dust_l[3:VH + 3, 3:VW + 3, None] * dust * .7
        # text legibility: dim the scene slightly behind the quote block
        img *= vign * (1 - .25 * np.exp(-((v - .42) / .22) ** 2))[..., None]
        ff.stdin.write((np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    out = f"{OUTDIR}/unseen_depth_quote_{i:02d}.mp4"
    compose(content, out)
    return out

if __name__ == "__main__":
    ids = [int(a) for a in sys.argv[1:]] or range(1, len(REELS) + 1)
    for i in ids: print(render(i))
