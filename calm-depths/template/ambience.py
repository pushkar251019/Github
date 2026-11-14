#!/usr/bin/env python3
"""Calm Depths — royalty-free procedural ambience (ocean / rain / fireplace / forest wind).
Usage: ambience.py <theme> <seconds> <out.wav>"""
import sys, numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt
SR = 48000
rng = np.random.default_rng(7)

def band(x, lo=None, hi=None, order=4):
    if lo and hi: sos = butter(order, [lo, hi], "bandpass", fs=SR, output="sos")
    elif lo: sos = butter(order, lo, "highpass", fs=SR, output="sos")
    else: sos = butter(order, hi, "lowpass", fs=SR, output="sos")
    return sosfilt(sos, x)

def noise(n): return rng.standard_normal(n)

def wave_env(n, mean_period=9.0):
    t = np.arange(n) / SR; e = np.zeros(n); start = 0.0
    while start < n / SR + 10:
        per = mean_period * rng.uniform(0.75, 1.3); amp = rng.uniform(0.6, 1.0)
        rise, decay = per * 0.35, per * 0.85
        tt = t - start
        up = np.clip(tt / rise, 0, 1) ** 2
        down = np.exp(-np.clip(tt - rise, 0, None) / (decay / 3))
        e = np.maximum(e, amp * np.where(tt < 0, 0, np.where(tt < rise, up, down)))
        start += per
    return e

def ocean(sec):
    n = int(sec * SR); out = []
    for ch in range(2):
        e = wave_env(n) if ch == 0 else np.roll(wave_env(n), int(0.35 * SR))
        lo = band(np.cumsum(noise(n)) * 0.02, lo=20, hi=350)
        mid = band(noise(n), 350, 1600); hi = band(noise(n), lo=1600) ; hi = band(hi, hi=9000)
        x = lo * (0.35 + 0.65 * e) + mid * 0.5 * e ** 1.6 + hi * 0.35 * e ** 2.6
        out.append(x)
    return np.stack(out, 1)

def rain(sec):
    n = int(sec * SR); out = []
    for ch in range(2):
        x = band(noise(n), 400, 7000) * 0.4 + band(noise(n), lo=20, hi=300) * 0.2
        drops = (rng.random(n) < 0.0009) * rng.uniform(0.3, 1, n)
        x += band(np.convolve(drops, np.exp(-np.arange(300) / 40), "same"), lo=1500) * 0.6
        out.append(x)
    return np.stack(out, 1)

def fireplace(sec):
    n = int(sec * SR); out = []
    for ch in range(2):
        roar = band(noise(n), lo=40, hi=500) * (0.6 + 0.4 * np.sin(np.arange(n) / SR * 0.7 + ch))
        cr = (rng.random(n) < 0.00035) * rng.uniform(0.2, 1, n) ** 3
        crackle = band(np.convolve(cr, rng.standard_normal(200) * np.exp(-np.arange(200) / 25), "same"), lo=1200)
        out.append(roar * 0.5 + crackle * 3.0)
    return np.stack(out, 1)

def forest(sec):
    n = int(sec * SR); t = np.arange(n) / SR; out = []
    for ch in range(2):
        gust = 0.5 + 0.5 * np.sin(2 * np.pi * t / 11 + ch) * np.sin(2 * np.pi * t / 4.3)
        out.append(band(noise(n), 150, 2500) * (0.3 + 0.7 * gust) * 0.6)
    return np.stack(out, 1)

def main():
    theme, sec, path = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    x = {"ocean": ocean, "rain": rain, "fireplace": fireplace, "forest": forest}[theme](sec + 4)
    x = x[int(2 * SR): int(2 * SR) + int(sec * SR)]
    x = x / np.abs(x).max() * 0.7
    sf.write(path, x.astype(np.float32), SR, subtype="PCM_24")
    print("wrote", path)

if __name__ == "__main__":
    main()
