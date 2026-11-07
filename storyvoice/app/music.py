"""Royalty-free background music, synthesised on the fly to match mood.

Every track is generated from scratch with numpy (pads, arpeggios, drones,
drums), so there are no copyright issues. Music follows the narration: each
passage gets a bed in its own mood, crossfaded into the next."""
import wave
from pathlib import Path

import numpy as np

SR = 24000
A4 = 440.0

MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]

# mood -> (root midi, scale, progression of scale degrees, seconds per chord,
#          layers, brightness 0..1)
STYLES = {
    "calm":          (57, MAJOR, [0, 5, 3, 4], 6.0, {"pad"}, 0.3),
    "joyful":        (60, MAJOR, [0, 4, 5, 3], 2.5, {"pad", "arp", "pulse"}, 0.7),
    "sad":           (57, MINOR, [0, 5, 2, 6], 6.5, {"pad", "piano"}, 0.25),
    "suspense":      (50, MINOR, [0, 0, 5, 6], 4.0, {"drone", "heartbeat", "pad"}, 0.2),
    "horror":        (45, MINOR, [0, 1, 0, 6], 7.0, {"drone", "noise", "cluster"}, 0.1),
    "romantic":      (58, MAJOR, [0, 5, 1, 4], 5.0, {"pad", "piano"}, 0.4),
    "epic":          (50, MINOR, [0, 5, 2, 6], 3.0, {"pad", "drums", "brass"}, 0.6),
    "mystery":       (52, MINOR, [0, 3, 5, 4], 5.0, {"pad", "piano", "drone"}, 0.3),
    "inspirational": (55, MAJOR, [0, 4, 5, 3], 4.0, {"pad", "arp"}, 0.55),
    "whimsical":     (65, MAJOR, [0, 3, 4, 0], 2.0, {"arp", "pad", "bell"}, 0.8),
    "informative":   (60, MAJOR, [0, 3, 4, 3], 6.0, {"pad"}, 0.2),
}


def _f(midi: float) -> float:
    return A4 * 2 ** ((midi - 69) / 12)


def _lowpass(x: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return x
    c = np.cumsum(np.insert(x, 0, 0.0))
    y = (c[k:] - c[:-k]) / k
    return np.concatenate([np.full(k - 1, y[0]), y])


def _chord(root: int, scale: list[int], degree: int) -> list[int]:
    notes = []
    for step in (0, 2, 4):
        idx = degree + step
        notes.append(root + scale[idx % 7] + 12 * (idx // 7))
    return notes


def _pluck(freq: float, dur: float, decay: float = 4.0, harm: float = 0.3) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    env = np.exp(-decay * t) * np.minimum(1, t * 200)
    return env * (np.sin(2 * np.pi * freq * t) + harm * np.sin(4 * np.pi * freq * t))


def render(mood: str, duration: float, seed: int = 0) -> np.ndarray:
    root, scale, prog, bar, layers, bright = STYLES.get(mood, STYLES["calm"])
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    nbars = int(np.ceil(duration / bar)) + 1

    for b in range(nbars):
        chord = _chord(root, scale, prog[b % len(prog)])
        start = int(b * bar * SR)
        length = int(bar * 1.35 * SR)  # overlap for smooth chord changes
        if start >= n:
            break
        seg = slice(start, min(n, start + length))
        tt = t[seg] - b * bar
        win = np.sin(np.pi * np.clip(tt / (bar * 1.35), 0, 1)) ** 2

        if "pad" in layers:
            for i, m in enumerate(chord + [chord[0] - 12]):
                fr = _f(m)
                tone = sum(np.sin(2 * np.pi * fr * d * tt + rng.uniform(0, 6))
                           for d in (1.0, 1.003, 0.997)) / 3
                tone += bright * 0.25 * np.sin(4 * np.pi * fr * tt)
                out[seg] += win * tone * (0.14 if i < 3 else 0.18)

        if "brass" in layers:
            for m in chord:
                fr = _f(m)
                saw = sum(np.sin(2 * np.pi * fr * k * tt) / k for k in range(1, 6))
                out[seg] += win * saw * 0.05

        if "drone" in layers:
            fr = _f(root - 24)
            out[seg] += win * (np.sin(2 * np.pi * fr * tt) + 0.5 * np.sin(2 * np.pi * fr * 1.5 * tt)) * 0.12

        if "cluster" in layers:
            for semi in (0, 1, 6):
                out[seg] += win * np.sin(2 * np.pi * _f(root + semi) * tt *
                                         (1 + 0.002 * np.sin(2 * np.pi * 0.3 * tt))) * 0.05

        def place(sig, at):
            i0 = start + int(at * SR)
            if i0 >= n:
                return
            i1 = min(n, i0 + len(sig))
            out[i0:i1] += sig[: i1 - i0]

        if "arp" in layers:
            steps = 8
            for s in range(steps):
                m = chord[s % 3] + 12 * (1 if s % 4 >= 2 else 0)
                place(_pluck(_f(m + 12), bar / steps * 2, 5.0) * 0.10, s * bar / steps)
        if "bell" in layers:
            place(_pluck(_f(chord[2] + 24), 2.0, 2.0, 0.6) * 0.06, bar / 2)
        if "piano" in layers:
            for s, m in enumerate([chord[0], chord[2], chord[1] + 12, chord[2]]):
                place(_pluck(_f(m + 12), 2.5, 2.5, 0.4) * 0.09, s * bar / 4 + rng.uniform(0, 0.05))
        if "pulse" in layers:
            for s in range(4):
                place(_pluck(_f(chord[0] - 12), 0.4, 9.0) * 0.12, s * bar / 4)
        if "heartbeat" in layers:
            for s in range(int(bar)):
                for off in (0.0, 0.25):
                    place(_pluck(55, 0.3, 14.0, 0) * 0.35, s + off)
        if "drums" in layers:
            for s in range(4):
                tt2 = np.arange(int(0.5 * SR)) / SR
                kick = np.sin(2 * np.pi * (45 + 60 * np.exp(-20 * tt2)) * tt2) * np.exp(-6 * tt2)
                place(kick * 0.35, s * bar / 4)

    if "noise" in layers:
        noise = _lowpass(rng.standard_normal(n), 60)
        swell = 0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t)
        out += noise * swell * 0.25

    out = _lowpass(out, max(1, int(6 * (1 - bright)) + 1))
    peak = np.max(np.abs(out)) or 1.0
    return out / peak * 0.5


def render_timeline(segments: list[tuple[str, float]], fade: float = 2.5) -> np.ndarray:
    """segments: [(mood, seconds)] -> one continuous crossfaded music bed.
    Consecutive passages with the same mood share a single track."""
    merged: list[list] = []
    for mood, dur in segments:
        if merged and merged[-1][0] == mood:
            merged[-1][1] += dur
        else:
            merged.append([mood, dur])
    total = int(sum(d for _, d in merged) * SR)
    out = np.zeros(total + int(fade * SR) + 1)
    pos = 0
    fn = int(fade * SR)
    for i, (mood, dur) in enumerate(merged):
        piece = render(mood, dur + fade, seed=i)
        env = np.ones(len(piece))
        if i > 0:
            env[:fn] = np.linspace(0, 1, fn)
        env[-fn:] = np.linspace(1, 0, fn)
        start = max(0, pos - (fn if i > 0 else 0) // 2)
        end = min(len(out), start + len(piece))
        out[start:end] += (piece * env)[: end - start]
        pos += int(dur * SR)
    return out[:total]


def write_wav(samples: np.ndarray, path: Path) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
