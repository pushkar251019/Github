# Unseen Depth of Life — Session Handoff

Paste the **Starter prompt** at the bottom into a new Claude Code session on your laptop.

## 1. Channel and brand (follow these on every post)
- **Page:** Unseen Depth of Life · **@unseen_depth_of_life** · brand hashtag **#unseendepth**
- **Positioning:** old wisdom in simple words. Calm mind, clear choices, inner strength. Indian spiritual (Krishna, Ram, Shiva, Hanuman, Lakshmi, Radha) meets a modern mindset. Audience: English and Hinglish speakers.
- **Goal:** 865 followers (audit of 22 Oct 2026) → 5,000. The full playbook is the artifact linked in the `unseen-depth-content` skill.
- **What works (from your page's own data):** a recognisable deity plus ONE original line on screen (the Krishna reel got 6,391 views); meaning beats mood (the Shiv Stuti with word meanings got 2,911); question hooks like "Who calms me?" (2,449, which is 12× your median). Run these as a numbered "Who…? #n" series.
- **What to avoid:** deity visuals with no message, English text on a plain dark background alone, off-brand cartoons, "psychology tricks", generic quote-page content, and quoting others (Rumi, Sadhguru, Jung) without your own line. Always add an original line signed **"— Unseen Depth"**.
- **Content pillars:** Deity + One Truth 40% · Question Hooks 25% (Wednesdays) · Calm Mind Lines carousels 20% (Saturdays) · The Unseen Man avatar 15%.
- **Cadence:** 5 feed posts a week (4 reels + 1 carousel) and a story daily. Plan festival reels 2 weeks ahead.
- **Visual style:** dark lamp cards (serif headline, 2–3 saffron words) and cinematic deity reels. @handle on every slide. Reels loop back to their first frame.
- **Every post follows the `instagram-post` format:** on-screen text with a hook in the first 1.5 s → a separate caption (hook line, 2–4 short lines, one CTA to save, send or comment, no hashtags in it) → **exactly 5 hashtags** (1 large, 2 mid-size, 1 niche, #unseendepth) → best posting time (IST), audio suggestion and alt text.

## 2. Brand frame (use for all videos)
- **Source:** `meditation/brand/frame_source.png`. A yellow-saffron frame with "UNSEEN DEPTH OF LIFE" at the top, a lantern at top-left, a man with a dog watching the sunrise at the bottom, and a transparent rounded window in the centre.
- **My additions:** the @unseen_depth_of_life handle under the title, a soft inner shadow on the window, a flickering lantern and a gently glowing sun.
- **Window:** x=36, y=282, 1008×1214 px on a 1080×1920 canvas (`brand/frame.json`).
- **Tool:** `python3 meditation/frame_template.py compose in.mp4 out.mp4` puts any video into the window.

## 3. What has been made
| Item | File | Status |
|---|---|---|
| Guided meditation reel "A Minute of Stillness" (89 s, narration with word-highlighted captions, breathing ring) | `meditation/unseen_depth_of_life_reel.mp4` | Delivered |
| 10 quote reels (13–17 s, hook → word-by-word quote → original line → save CTA, diya lamp scene) | `meditation/quotes/unseen_depth_quote_01..10.mp4` | Delivered; posting in progress |
| Posting plan with captions, hashtags and alt text for all 10 | `meditation/quotes/POSTING_PLAN.md` | Done |
| Generator scripts | `make_reel.py`, `make_quotes.py`, `frame_template.py` | On branch `reel-unseen-depth-of-life` |

**Posting status (13 Nov 2026):** 3 reels posted, the 4th (`quote_02`, "Why do answers come…") posting today. Plan order: 01, 03, 04, 02, 05, 07, 06, 08, 09, 10.
- The quotes came from "I spent 748 Days to Find the 300 Best Motivational Quotes" (your Google Drive). 313 quotes were extracted. **Only the quote text is used**; that creator's footage, voice and music are not, to avoid copyright claims.
- Next batch candidates are at the end of `POSTING_PLAN.md`.

## 4. Your instructions (must follow)
1. **Do NOT change the current 10 quote reels.** Their audio, visuals and files stay as they are.
2. **Change the background sound in UPCOMING videos only** (after these 10 are posted). Options to offer: tanpura drone, bansuri flute over tanpura, soft piano with rain, or a track from Instagram's music library added in-app (the quote reels have no voiceover, so this is easy and can help reach). Ask which one before building.
3. **B-roll task (next):** use your iPhone clips in `C:\Users\pushk\OneDrive\Desktop\Iphone`:
   - cut out unusable parts (shaky starts and ends, blur, dark sections, dead time);
   - save the clean clips in a **separate folder** (e.g. `...\Iphone\broll_clean\`), ready to drop into any content;
   - name them by scene (`sunrise_01.mp4`, `walk_road_02.mp4`), export a vertical 1080×1920 version and a 1008×1214 frame-window version, apply a consistent warm grade, and make a muted copy plus one with the original sound;
   - add a contact sheet or index;
   - **never modify or delete the originals.**
4. Other laptop folders: `Unseen Depth` and `Youtube`.
5. Keep replies short (3–4 lines). Use numbered or bulleted points, give recommendations, and separate facts from assumptions.

## 5. Technical prerequisites (laptop)
- Git, and this repo cloned: `git clone https://github.com/pushkar251019/github` → `git checkout reel-unseen-depth-of-life`
- **Python 3.10+** with `pip install numpy pillow piper-tts`
- **ffmpeg** on PATH (`winget install Gyan.FFmpeg`), built with libass (the default builds have it)
- **Fonts:** in `meditation/fonts/` (Cormorant Garamond for serif headlines, Inter for captions). On Windows, install them (right-click → Install) so ffmpeg's subtitle renderer finds them.
- **Narration voice:** the Piper `en-us-lessac-medium` voice downloads automatically from GitHub on the first run of `make_reel.py`. It's clear but slightly robotic; recording your own voice, or a premium voice service, would sound better.
- The scripts were written on Linux and use `~/.fonts` + `fc-cache`. On Windows, skip that step and install the fonts instead.

## 6. Insights and recommendations
- **Measure saves and shares per reel, not views.** After 5 posts, double down on the hook style that earned the most saves.
- **Biggest growth lever per your data:** deity + one original truth. The current batch has no deity visuals, so the next batch should test 2–3 deity reels in the frame (e.g. Krishna + "Who calms me? #2").
- **Wednesdays get the strongest question hooks.**
- **Quote credit:** cite an author only when certain (Seneca, Marcus Aurelius). Many viral quotes are misattributed; leave those uncredited and pair them with your own line.
- **Large media in git:** MP4s are committed directly, about 100 MB so far. Use Git LFS or keep renders out of git before the library grows.
- **Posting time (estimate):** 8 PM IST on weekdays, 9 AM IST on Sundays. Check against Instagram Insights.

---

## Starter prompt (paste into the new session)
```
I run the Instagram page "Unseen Depth of Life" (@unseen_depth_of_life). Read meditation/HANDOFF.md in
https://github.com/pushkar251019/github (branch reel-unseen-depth-of-life) and follow it.
Load my unseen-depth-content and instagram-post skills.
Task now: my raw iPhone clips are in C:\Users\pushk\OneDrive\Desktop\Iphone. Trim unusable parts
and save cleaned, scene-named B-roll in a separate folder (vertical 1080x1920 + 1008x1214 frame-window
versions, warm grade, muted + original-audio copies, contact sheet). Never touch the originals.
Do not change the 10 existing quote reels. New background sound applies only to upcoming videos — ask me which style first.
```
