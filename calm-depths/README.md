# Calm Depths: Master Intro Template

*Escape the noise. Find your calm.* · Sounds • Mindfulness • Inner Calm

## Deliverables

| # | Deliverable | File |
|---|---|---|
| 1 | 45 s intro (H.264 High, AAC 48 kHz, 1920×1080, 30 fps, fast-start) | `exports/CalmDepths_Intro_ocean.mp4` |
| 1b | YouTube caption file | `exports/CalmDepths_Intro_captions.srt` |
| 2 | Female voiceover (WAV 48 kHz/24-bit + MP3 320k) | `assets/voice/CalmDepths_Narrator_Intro.wav` / `.mp3` |
| 3 | Reusable template (this folder) | `build.sh`, `template/` |
| 4 | Transparent logo, emblem, watermark, YouTube brand stamp, profile picture | `assets/brand/*.png` |
| 5 | Subscribe animation (transparent) | `assets/brand/CalmDepths_Subscribe_5s_alpha.mov` (ProRes 4444), `.webm` (VP9 alpha), `_60s_cycle_alpha.mov` |

## What stays locked, and what changes per video
**Locked:** narrator (`template/narrator_profile.json`, master WAV reused unchanged), exact script, caption words, timing and gold highlights (`render_intro.py`), logo, colours and fonts (`brand.py`), subscribe animation, audio mix, 45 s structure.
**Changes per video:** background footage and colour grade (`template/themes/<theme>.json`) and ambience (`template/ambience.py`).

## Intro timeline (45.0 s)
0–1.2 s fade in from black · 0.6–7.6 s logo reveal (emblem, CALM DEPTHS with letters settling, descriptor with gold hairlines) · 2.2–41.2 s narration with synchronised captions · 7.4–40 s corner watermark · 26.5–32.5 s gold breathing ring · 41–44.9 s brand stamp, tagline, then YouTube play mark, SUBSCRIBE → SUBSCRIBED and a bell ring · ambience swells after the narration ends.

## Make a new intro
```bash
pip install numpy pillow scipy soundfile        # one time
# 1. put footage in footage/ and set "footage", "shots", "grade" and "footage_credit" in template/themes/<theme>.json
./build.sh rain                                 # → exports/CalmDepths_Intro_rain.mp4
```
To brand a full ambience video (intro in front with a 1.5 s crossfade, watermark throughout, subscribe about every 60 s):
```bash
python3 template/brand_long_video.py my_rain_3h.mp4 final.mp4 --intro exports/CalmDepths_Intro_rain.mp4
python3 template/export_assets.py               # regenerates all brand PNGs/animations
```

## Licences and credits (required)
- **Ocean footage:** "Coucher de soleil sur la plage de Nabeul, 10 novembre 2017" by **Habib M'henni**, via Wikimedia Commons, **CC BY 3.0**. Paste this in every YouTube description that uses it:
  `Ocean footage: Habib M'henni, "Coucher de soleil sur la plage de Nabeul" (CC BY 3.0), via Wikimedia Commons.`
- Voice: Kokoro-82M (Apache-2.0). Fonts: Cormorant Garamond and Montserrat (SIL OFL). Ambience: generated in code, so it is royalty-free.
