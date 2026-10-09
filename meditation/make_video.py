"""Generate a 2-minute guided-breathing meditation music video (720p, 24fps)."""
import subprocess, wave, numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR, SR = 1280, 720, 24, 120, 44100
BREATH = 10.0  # 4s inhale, 1s hold, 4s exhale, 1s hold -> ~6 breaths/min
OUT = "/home/user/Github/meditation/meditation.mp4"
rng = np.random.default_rng(7)

# ---------------- AUDIO ----------------
t = np.arange(int(SR * DUR)) / SR
def env_fade(x):
    f = np.minimum(1, np.minimum(t / 6, (DUR - t) / 8)); return x * f
# Drone: A2 root + fifth + octave, slow beating (binaural offset L/R)
drone_L = sum(a*np.sin(2*np.pi*f*t) for f, a in [(110,.30),(165,.15),(220,.10),(55,.20)])
drone_R = sum(a*np.sin(2*np.pi*(f+0.6)*t) for f, a in [(110,.30),(165,.15),(220,.10),(55,.20)])
swell = 0.75 + 0.25*np.sin(2*np.pi*t/BREATH - np.pi/2)  # pad breathes with visuals
drone_L *= swell; drone_R *= swell
# Ocean-like filtered noise
noise = np.cumsum(rng.standard_normal(len(t))); noise -= np.convolve(noise, np.ones(400)/400, 'same')
noise /= np.abs(noise).max(); waves = noise * (0.5+0.5*np.sin(2*np.pi*t/13))**2 * 0.12
# Singing bowls (inharmonic partials, long decay) every 20s
bowls = np.zeros_like(t)
for start in np.arange(0.5, DUR-10, 20):
    i = int(start*SR); tt = t[:len(t)-i]
    b = sum(a*np.sin(2*np.pi*f*tt)*np.exp(-tt/d) for f,a,d in [(220,.5,9),(592,.3,6),(1105,.15,4),(1770,.07,2.5)])
    bowls[i:] += b * 0.35 * (1 - np.exp(-tt*80))
# Pentatonic chimes (A minor pentatonic), sparse random
chimes = np.zeros_like(t); notes = [440,523.25,587.33,659.25,783.99,880]
for start in np.sort(rng.uniform(8, DUR-8, 28)):
    i = int(start*SR); n = min(int(4*SR), len(t)-i); tt = t[:n]; f = rng.choice(notes)
    chimes[i:i+n] += (np.sin(2*np.pi*f*tt)+.3*np.sin(2*np.pi*f*2.01*tt))*np.exp(-tt/1.2)*0.06*(1-np.exp(-tt*200))
L = env_fade(drone_L + waves + bowls + chimes*0.9); R = env_fade(drone_R + waves + bowls + chimes*1.1)
st = np.stack([L, R], 1); st = st / np.abs(st).max() * 0.85
with wave.open("/tmp/claude-0/med_audio.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st*32767).astype(np.int16).tobytes())

# ---------------- VIDEO ----------------
y, x = np.mgrid[0:H, 0:W].astype(np.float32)
cx, cy = W/2, H/2 - 20
dx, dy = (x-cx)/H, (y-cy)/H
r = np.sqrt(dx**2 + dy**2); ang = np.arctan2(dy, dx)
stars = (rng.random((H, W)) > 0.9985).astype(np.float32) * rng.random((H, W)).astype(np.float32)

def breath_phase(s):  # 0..1 orb size following inhale/hold/exhale/hold
    p = s % BREATH
    if p < 4: return 0.5 - 0.5*np.cos(np.pi*p/4)
    if p < 5: return 1.0
    if p < 9: return 0.5 + 0.5*np.cos(np.pi*(p-5)/4)
    return 0.0
def label(s):
    p = s % BREATH
    return "Breathe in" if p < 4 else "Hold" if p < 5 else "Breathe out" if p < 9 else ""

try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf", 40)
except OSError: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
def text_mask(s, size=None):
    f = font if size is None else ImageFont.truetype(font.path, size)
    img = Image.new("L", (W, 120), 0); d = ImageDraw.Draw(img)
    bw = d.textlength(s, font=f); d.text(((W-bw)/2, 30), s, fill=255, font=f)
    return np.asarray(img, np.float32)/255
masks = {s: text_mask(s) for s in ["Breathe in", "Hold", "Breathe out", ""]}
title = text_mask("Be here now", 56); outro = text_mask("Carry this stillness with you", 40)

ff = subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}",
    "-r",str(FPS),"-i","-","-i","/tmp/claude-0/med_audio.wav","-c:v","libx264","-preset","medium","-crf","20",
    "-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",OUT], stdin=subprocess.PIPE)

for fi in range(DUR*FPS):
    s = fi / FPS; b = breath_phase(s)
    hue = s/DUR  # drift deep indigo -> teal -> violet
    c1 = np.array([0.05+0.04*np.sin(2*np.pi*hue), 0.04+0.05*np.sin(2*np.pi*hue+2), 0.14], np.float32)
    bg = c1 * (1.3 - r[...,None]*0.9)
    R0 = 0.12 + 0.10*b
    orb = np.exp(-(r/R0)**2*1.6)
    halo = np.exp(-r/(R0*2.2))*0.35
    petals = (0.5+0.5*np.cos(8*(ang + s*0.05)))**6 * np.exp(-((r-R0*1.5)/(0.09))**2) * 0.35
    petals2 = (0.5+0.5*np.cos(12*(ang - s*0.03)))**8 * np.exp(-((r-R0*2.3)/(0.06))**2) * 0.22
    rings = (0.5+0.5*np.sin(r*40 - s*1.2))**12 * np.exp(-r*2.5) * 0.12
    twinkle = stars * (0.5+0.5*np.sin(s*1.5 + x*0.01 + y*0.013))
    gold = np.array([1.0, 0.82, 0.55], np.float32); teal = np.array([0.45, 0.85, 1.0], np.float32)
    col = np.array([0.75, 0.6, 1.0], np.float32)
    img = bg + orb[...,None]*gold + halo[...,None]*teal*0.6 + (petals+petals2)[...,None]*col + rings[...,None]*teal + twinkle[...,None]*0.8
    # text: breathing cue under orb, title/outro
    p = s % BREATH; ta = min(1, p/0.6, max(0, (4 if p<4 else 5 if p<5 else 9 if p<9 else 10) - p)/0.6)
    cue_alpha = ta * np.clip((s-8)/3, 0, 1) * np.clip((DUR-14-s)/3, 0, 1) * 0.85
    y0 = H-170; img[y0:y0+120] += masks[label(s)][...,None] * cue_alpha
    ti = np.clip(min(s-0.5, 7.5-s)/1.5, 0, 1); img[60:180] += title[...,None]*ti*0.9
    to = np.clip(min(s-(DUR-12), DUR-1-s)/2, 0, 1); img[y0:y0+120] += outro[...,None]*to*0.85
    fade = min(1, s/4, (DUR-s)/3)
    ff.stdin.write((np.clip(img*fade, 0, 1)*255).astype(np.uint8).tobytes())
ff.stdin.close(); ff.wait(); print("done", OUT)
