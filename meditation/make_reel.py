"""Instagram Reel: 'A Minute of Stillness' guided breathing meditation for Unseen Depth of Life.

Output: 1080x1920 @30fps H.264 + AAC, loudness-normalised for Instagram (-14 LUFS).
Pipeline: Piper TTS narration -> timeline -> synth music bed (ducked, breath-synced)
          -> numpy visuals at half-res -> ffmpeg upscale + libass captions/branding.
Usage: python3 make_reel.py [--preview SECONDS]
"""
import os, subprocess, sys, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.environ.get("REEL_TMP", "/tmp/claude-0/reel")
VOICE = os.environ.get("PIPER_VOICE", "/tmp/claude-0/voice/en-us-lessac-medium.onnx")
OUT = os.path.join(HERE, "unseen_depth_of_life_reel.mp4")
W, H, FPS, SR = 1080, 1920, 30, 44100
VW, VH = W // 2, H // 2          # visuals rendered at half-res, upscaled by ffmpeg
BRAND = "Unseen Depth of Life"
INHALE, HOLD, EXHALE = 4.0, 2.0, 5.0
os.makedirs(TMP, exist_ok=True)

# (kind, caption, spoken text / breath lines, pause after)
SCRIPT = [
    ("say", "Pause for a moment.", "Pause, for a moment.", 0.7),
    ("say", "This next minute is just for you.", "This next minute, is just for you.", 1.2),
    ("say", "Get comfortable. Gently close your eyes… or soften your gaze on the light.",
            "Get comfortable. Gently close your eyes, or soften your gaze on the light.", 1.0),
    ("say", "Let your shoulders drop. Unclench your jaw.", "Let your shoulders drop. Unclench your jaw.", 1.3),
    ("say", "Now, breathe with the light.", "Now, breathe with the light.", 0.6),
    ("breath", ("Breathe in…", "Hold…", "And slowly breathe out.")),
    ("breath", ("In… filling your body with calm.", "Hold.", "Out… releasing what you don't need.")),
    ("breath", ("In…", "Hold.", "Out…")),
    ("say", "Notice the stillness beneath your thoughts.", "Notice the stillness, beneath your thoughts.", 1.6),
    ("say", "Beneath every noise, there is a quiet depth within you.",
            "Beneath every noise, there is a quiet depth within you.", 0.9),
    ("say", "It has always been here.", "It has always been here.", 1.8),
    ("say", "One last breath.", "One last breath.", 0.4),
    ("breath", ("In…", "Hold.", "And let it all go.")),
    ("say", "Gently open your eyes.", "Gently open your eyes.", 0.9),
    ("say", "Carry this calm with you today.", "Carry this calm with you today.", 1.2),
]
INTRO = 1.4   # visuals + bowl before first word
OUTRO = 5.5   # end card

# ---------------- narration ----------------
def tts(text, idx):
    path = f"{TMP}/line_{idx:02d}.wav"
    if not os.path.exists(path):
        subprocess.run([sys.executable, "-m", "piper", "-m", VOICE, "-f", path,
                        "--length-scale", "1.18", "--noise-scale", "0.55", "--sentence-silence", "0.25"],
                       input=text.encode(), check=True, capture_output=True)
    with wave.open(path) as w:
        sr, x = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768.0
    x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x)  # -> 44.1k
    nz = np.nonzero(np.abs(x) > 0.01)[0]                                              # trim silence
    return x[max(0, nz[0] - 400): nz[-1] + 2000] if len(nz) else x

clips, events, breaths = [], [], []   # clips: (start, audio); events: caption (start, end, text, speech_dur)
t, n = INTRO, 0
for item in SCRIPT:
    if item[0] == "say":
        _, cap, spoken, pause = item
        a = tts(spoken, n); n += 1; d = len(a) / SR
        clips.append((t, a)); events.append((t, t + d + min(pause, 0.5), cap, d)); t += d + pause
    else:
        t0 = t; breaths.append(t0)
        for off, dur, line in zip((0, INHALE, INHALE + HOLD), (INHALE, HOLD, EXHALE), item[1]):
            a = tts(line.replace("…", ","), n); n += 1; d = len(a) / SR
            clips.append((t0 + off + 0.1, a)); events.append((t0 + off + 0.1, t0 + off + dur - 0.1, line, d))
        t = t0 + INHALE + HOLD + EXHALE + 0.8
END_CARD = t + 0.3
DUR = END_CARD + OUTRO
print(f"duration {DUR:.1f}s, {len(clips)} voice clips")

# breath curve b(t): 0.18 idle -> 1 full
def breath_state(s):
    for t0 in breaths:
        p = s - t0
        if 0 <= p < INHALE: return 0.18 + 0.82 * (0.5 - 0.5 * np.cos(np.pi * p / INHALE)), "INHALE", p / INHALE
        if INHALE <= p < INHALE + HOLD: return 1.0, "HOLD", (p - INHALE) / HOLD
        if INHALE + HOLD <= p < INHALE + HOLD + EXHALE:
            q = (p - INHALE - HOLD) / EXHALE; return 0.18 + 0.82 * (0.5 + 0.5 * np.cos(np.pi * q)), "EXHALE", q
    return 0.18 + 0.04 * np.sin(2 * np.pi * s / 6), None, 0.0

# ---------------- audio ----------------
N = int(SR * DUR); ts = np.arange(N) / SR; rng = np.random.default_rng(11)
voice = np.zeros(N)
for st, a in clips:
    i = int(st * SR); voice[i:i + len(a)] += a[:N - i]
ir_t = np.arange(int(1.4 * SR)) / SR                              # small-hall reverb
ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t / 0.35); ir[0] = 0
L2 = 1 << int(np.ceil(np.log2(N + len(ir))))
wet = np.fft.irfft(np.fft.rfft(voice, L2) * np.fft.rfft(ir, L2), L2)[:N]
voice = voice / np.abs(voice).max() * 0.9; wet = wet / np.abs(wet).max() * 0.9
voice_mix = voice + 0.12 * wet

bcurve = np.interp(ts, np.arange(0, DUR, 1 / FPS), [breath_state(s)[0] for s in np.arange(0, DUR, 1 / FPS)])
drone = lambda off: sum(a * np.sin(2 * np.pi * (f + off) * ts) for f, a in [(55, .22), (110, .30), (164.8, .14), (220, .08), (329.6, .03)])
pad = 0.65 + 0.35 * bcurve
noise = np.cumsum(rng.standard_normal(N)); noise -= np.convolve(noise, np.ones(500) / 500, "same")
waves = noise / np.abs(noise).max() * (0.5 + 0.5 * np.sin(2 * np.pi * ts / 11)) ** 2 * 0.10
bowls = np.zeros(N)
for st in [0.2, breaths[0], next(e[0] for e in events if e[2].startswith("Notice")) - 0.4, END_CARD]:
    i = int(st * SR); tt = ts[:N - i]
    bowls[i:] += sum(a * np.sin(2 * np.pi * f * tt) * np.exp(-tt / d) for f, a, d in
                     [(220, .5, 9), (592, .3, 6), (1105, .15, 4), (1770, .07, 2.5)]) * 0.32 * (1 - np.exp(-tt * 80))
chimes = np.zeros(N)
for st in np.sort(rng.uniform(6, DUR - 4, 22)):
    i = int(st * SR); m = min(int(4 * SR), N - i); tt = ts[:m]; f = rng.choice([440, 523.25, 587.33, 659.25, 783.99, 880])
    chimes[i:i + m] += (np.sin(2 * np.pi * f * tt) + .3 * np.sin(2 * np.pi * f * 2.01 * tt)) * np.exp(-tt / 1.2) * .05 * (1 - np.exp(-tt * 200))
venv = np.convolve(np.abs(voice), np.ones(int(.25 * SR)) / int(.25 * SR), "same"); venv = np.clip(venv / venv.max() * 4, 0, 1)
duck = 1 - 0.5 * venv
music_L = (drone(0) * pad + waves + chimes * .9) * duck + bowls
music_R = (drone(0.5) * pad + waves + chimes * 1.1) * duck + bowls
music_L /= np.abs(music_L).max(); music_R /= np.abs(music_R).max()
fade = np.minimum(1, np.minimum(ts / 1.0, (DUR - ts) / 3.0))
mix = np.stack([voice_mix + 0.32 * music_L, voice_mix + 0.32 * music_R], 1) * fade[:, None]
mix = mix / np.abs(mix).max() * 0.89
with wave.open(f"{TMP}/mix.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())

# ---------------- captions / branding (ASS) ----------------
def ts_ass(s): s = max(0, s); return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"
def karaoke(text, speech):
    words = text.split(); w = np.array([len(x) + 2 for x in words], float); cs = w / w.sum() * speech * 100
    return " ".join(f"{{\\kf{int(c)}}}{x}" for c, x in zip(cs, words))
ass = [f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter SemiBold,58,&H00FFFFFF,&H90E8C8D8,&H70100818,&H96000000,0,0,0,0,100,100,0,0,1,2.2,3,8,110,110,1360,1
Style: Phase,Inter Medium,30,&H00F2E6D9,&H00FFFFFF,&H80100818,&H00000000,0,0,0,0,100,100,10,0,1,1.2,0,8,0,0,1250,1
Style: Brand,Cormorant Garamond,52,&H20FFFFFF,&H00FFFFFF,&H90100818,&H00000000,0,1,0,0,100,100,1,0,1,1.4,0,7,64,0,236,1
Style: Over,Inter Medium,30,&H00E6D3F5,&H00FFFFFF,&H80100818,&H00000000,0,0,0,0,100,100,14,0,1,1.2,0,8,0,0,470,1
Style: Title,Cormorant Garamond,118,&H00FFFFFF,&H00FFFFFF,&H80100818,&H00000000,0,0,0,0,100,100,0,0,1,1.8,2,8,60,60,520,1
Style: Sub,Inter Light,38,&H20F2E6D9,&H00FFFFFF,&H80100818,&H00000000,0,0,0,0,100,100,2,0,1,1.2,0,8,60,60,680,1
Style: End,Cormorant Garamond,92,&H00FFFFFF,&H00FFFFFF,&H80100818,&H00000000,0,1,0,0,100,100,0,0,1,1.8,2,8,60,60,1290,1
Style: CTA,Inter Medium,40,&H00F2E6D9,&H00FFFFFF,&H80100818,&H00000000,0,0,0,0,100,100,3,0,1,1.2,0,8,60,60,1420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""]
def ev(a, b, style, text, layer=0): ass.append(f"Dialogue: {layer},{ts_ass(a)},{ts_ass(b)},{style},,0,0,0,,{text}")
ev(0.3, DUR, "Brand", r"{\fad(800,600)}◦ " + BRAND)
ev(0.5, 7.2, "Over", r"{\fad(600,500)}GUIDED BREATHING MEDITATION")
ev(0.8, 7.2, "Title", r"{\fad(900,500)\blur0.6}A Minute of Stillness")
ev(1.4, 7.2, "Sub", r"{\fad(700,500)}breathe with the light")
for a, b, text, sp in events:
    ev(a, b, "Cap", r"{\fad(220,260)}" + karaoke(text, sp * 0.95))
for t0 in breaths:
    for off, dur, name in ((0, INHALE, "INHALE"), (INHALE, HOLD, "HOLD"), (INHALE + HOLD, EXHALE, "EXHALE")):
        for k in range(int(dur)):
            ev(t0 + off + k, t0 + off + k + 1, "Phase", f"{{\\fad({150 if k == 0 else 0},{150 if k == dur - 1 else 0})}}{name}   {int(dur) - k}")
ev(END_CARD, DUR, "End", r"{\fad(900,400)}" + BRAND)
ev(END_CARD + 0.8, DUR, "CTA", r"{\fad(700,400)}Save this for when you need a pause")
ev(END_CARD + 1.6, DUR, "CTA", r"{\fad(700,400)\pos(540,1500)}Follow for your daily moment of stillness")
open(f"{TMP}/captions.ass", "w").write("\n".join(ass) + "\n")

# ---------------- visuals ----------------
y, x = np.mgrid[0:VH, 0:VW].astype(np.float32)
cx, cy = VW / 2, VH * 0.47
dx, dy = (x - cx) / VW, (y - cy) / VW
r = np.sqrt(dx ** 2 + dy ** 2); ang = np.arctan2(dy, dx)
ang_top = ((np.arctan2(dx, -dy)) % (2 * np.pi)) / (2 * np.pi)       # 0 at 12 o'clock, clockwise
vign = np.clip(1.25 - 0.9 * np.sqrt(((x - VW / 2) / VW) ** 2 + ((y - VH * 0.5) / VH * 1.2) ** 2) * 1.6, 0.15, 1)[..., None]
stars = ((rng.random((VH, VW)) > 0.9975) * rng.random((VH, VW))).astype(np.float32)
NP = 70; px, py = rng.uniform(0, VW, NP), rng.uniform(0, VH, NP); pv = rng.uniform(4, 14, NP); pp = rng.uniform(0, 6.3, NP); pa = rng.uniform(.15, .5, NP)
sg = np.exp(-(np.mgrid[-4:5, -4:5] ** 2).sum(0) / 4.0).astype(np.float32)
GOLD, TEAL, VIOLET = (np.array(c, np.float32) for c in ([1.0, .84, .60], [.45, .86, 1.0], [.74, .60, 1.0]))
PHASE_COL = {"INHALE": TEAL, "HOLD": GOLD, "EXHALE": VIOLET}

preview = float(sys.argv[sys.argv.index("--preview") + 1]) if "--preview" in sys.argv else None
render_dur = min(DUR, preview) if preview else DUR
vf = (f"scale={W}:{H}:flags=lanczos,ass={TMP}/captions.ass:fontsdir={HERE}/fonts,"
      f"noise=alls=3:allf=t,format=yuv420p")
out = OUT if not preview else f"{TMP}/preview.mp4"
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}",
    "-r", str(FPS), "-i", "-", "-i", f"{TMP}/mix.wav", "-t", f"{render_dur:.2f}", "-vf", vf,
    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high",
    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out], stdin=subprocess.PIPE)

for fi in range(int(render_dur * FPS)):
    s = fi / FPS; b, phase, prog = breath_state(s)
    hue = s / DUR
    base = np.array([.045 + .03 * np.sin(2 * np.pi * hue), .035 + .03 * np.sin(2 * np.pi * hue + 2), .12], np.float32)
    bg = base * (1.25 - r[..., None] * 1.1) + np.array([.05, .02, .08], np.float32) * np.clip(dy * 1.4, 0, 1)[..., None]
    R0 = 0.07 + 0.075 * b
    orb = np.exp(-(r / R0) ** 2 * 1.7)
    halo = np.exp(-r / (R0 * 2.0)) * (0.25 + 0.2 * b)
    pet = (.5 + .5 * np.cos(8 * (ang + s * .06))) ** 6 * np.exp(-((r - R0 * 1.6) / .055) ** 2) * (.25 + .2 * b)
    pet2 = (.5 + .5 * np.cos(12 * (ang - s * .035))) ** 8 * np.exp(-((r - R0 * 2.4) / .04) ** 2) * .18
    rings = (.5 + .5 * np.sin(r * 55 - s * 1.1)) ** 14 * np.exp(-r * 3) * .10
    img = bg + orb[..., None] * GOLD + halo[..., None] * TEAL * .55 + (pet + pet2)[..., None] * VIOLET + rings[..., None] * TEAL
    ring_r = 0.30                                                     # breath progress arc
    track = np.exp(-((r - ring_r) / .004) ** 2)
    img += track[..., None] * .07
    if phase:
        arc = track * (ang_top <= prog) * 1.0
        head = np.exp(-((dx - ring_r * np.sin(2 * np.pi * prog)) ** 2 + (dy + ring_r * np.cos(2 * np.pi * prog)) ** 2) / .00012)
        img += (arc * .8 + head * .9)[..., None] * PHASE_COL[phase]
    img += (stars * (.5 + .5 * np.sin(s * 1.3 + x * .02 + y * .03)))[..., None] * .7
    pyy = (py - pv * s) % VH; pxx = (px + 6 * np.sin(s * .4 + pp)) % VW
    dust = np.zeros((VH + 9, VW + 9), np.float32)
    for k in range(NP):
        iy, ix = int(pyy[k]), int(pxx[k]); dust[iy:iy + 9, ix:ix + 9] += sg * pa[k] * (.6 + .4 * np.sin(s + pp[k]))
    img += dust[4:VH + 4, 4:VW + 4, None] * GOLD * .5
    img *= vign
    # dim the title card area slightly for legibility; fade in/out
    f = min(1, s / 1.0, (DUR - s) / 1.5) * (1 - 0.35 * np.clip(1 - abs(s - 4) / 3.5, 0, 1) * (s < 7.5))
    ff.stdin.write((np.clip(img * f, 0, 1) * 255).astype(np.uint8).tobytes())
ff.stdin.close(); ff.wait(); print("wrote", out)
