# Studio: self-hosted voice, image & long-form video

A credit-free alternative to Higgsfield and ElevenLabs. It runs on your own GPU,
or on a rented one, using open models you are allowed to use commercially.

| Feature | Model / source | Licence | Hardware |
|---|---|---|---|
| Voiceover (stock voices, incl. Hindi) | Kokoro | Apache-2.0 | CPU OK |
| Voice clone from a 10–20s sample | Chatterbox | MIT | GPU recommended |
| Images | FLUX.1-schnell | Apache-2.0 | GPU 12GB+ |
| AI video clips (text/image → video) | LTX-Video, Wan 2.2 5B | open weights* | NVIDIA 12–24GB |
| On-camera "you" (lip-sync on your footage) | LatentSync | Apache-2.0 | NVIDIA 8GB+ |
| Captions (.srt) | faster-whisper | MIT | CPU OK |
| Royalty-free B-roll & photos | Pexels + Pixabay APIs | free commercial use | — |
| **Long video (any length, 30+ min)** | all of the above + ffmpeg | — | CPU edit; GPU only for AI scenes |

\*Check each model card before commercial use. Licences change.

## How the 30-minute videos work
No model, paid or open, renders 30 minutes in one go. Paid tools make 5–15s clips.
Long videos are **assembled**, and this app automates the assembly:

1. Write a script. Each paragraph is one scene.
2. Each paragraph is voiced (stock voice or your clone).
3. Each scene gets a visual, set by a tag at the start of the paragraph:
   - `[broll: ocean waves at dawn]` downloads stock footage from Pexels/Pixabay
   - `[ai: monk meditating in mist]` generates a clip with LTX/Wan
   - `[library]` uses your own uploaded B-roll (random start point, so reuse doesn't look repetitive)
   - `[avatar]` lip-syncs your face footage to the line
   - no tag: uses your library if it has clips, otherwise stock footage matched to keywords in the paragraph
4. Clips are trimmed or looped to the narration, photos get a slow Ken Burns zoom, and the scenes are joined.
5. Captions are made from the script text, so the wording is exact. Music is ducked under the voice.
6. Output: `.mp4` + `.srt` + `.credits.txt` (where each stock clip came from).

Tested: a 30-scene, 3.7-min 1080p build took about 3 minutes of editing time on a plain CPU.
A 30-min video should take about 25–30 min to edit, plus voice time, plus GPU time for any `[ai]` or `[avatar]` scenes.

## Setup
```bash
# 1. Install PyTorch for your hardware: https://pytorch.org/get-started/locally/
# 2. Install everything else and start the app
cd studio && ./run.sh          # opens on http://127.0.0.1:7860
```
Needs `ffmpeg` (`brew install ffmpeg` / `sudo apt install ffmpeg`) and **Python 3.10–3.12**.

Free stock-footage keys (2 minutes to get):
```bash
export PEXELS_API_KEY=...    # https://www.pexels.com/api/
export PIXABAY_API_KEY=...   # https://pixabay.com/api/docs/
```

Avatar scenes (optional): install [LatentSync](https://github.com/bytedance/LatentSync), then set
`LATENTSYNC_DIR` and `LATENTSYNC_PY` (see `engines.lipsync`). For best results, record 30–60s of
yourself facing the camera in good light, mouth always visible.

## Windows laptop (no NVIDIA GPU): the hybrid setup
For a typical laptop (e.g. i7 8th-gen, 16GB RAM, small AMD/Intel graphics):

**One-time install (PowerShell):**
```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
winget install Git.Git
git clone https://github.com/pushkar251019/Github.git
cd Github; git checkout claude/bold-bardeen-oz2qiu
```
Kokoro also needs **espeak-ng**: install the `.msi` from https://github.com/espeak-ng/espeak-ng/releases.
Then double-click **`studio\run.bat`**. It installs the laptop version on the first run and opens the app.

**On the laptop (free):** voiceovers, captions, stock search, and full long-form editing with stock footage or your own B-roll.
Exports automatically use the Intel QuickSync encoder when it's available, which is much faster than CPU encoding.
Close Chrome and other heavy apps while rendering.

**On a rented GPU (pay only while it's on):** voice cloning at speed, AI video clips (`[ai: …]`), images, and avatar scenes.
1. On RunPod or Vast.ai, start an RTX 4090 pod (24GB) with a PyTorch template.
2. In the pod terminal: `git clone` this repo, `cd studio && ./run.sh`, and open port 7860 through the pod's HTTP proxy.
3. Batch a session's worth of work, download the outputs, then **stop the pod**. Billing runs until you stop it.

Workflow that keeps costs near zero: write the script and build the full 30-min video on the laptop with stock footage and your
B-roll. Rent a GPU for an hour only when you want AI hero shots or avatar scenes, then drop those clips into **My B-roll**.

## Hardware: what you actually need
| Setup | What runs well | Rough cost |
|---|---|---|
| Any laptop (CPU) | Voice, captions, long-form editing with stock/your B-roll | Free |
| Mac M-series 16GB+ | + voice cloning, images (slow) | Free |
| NVIDIA RTX 4090 / 5090 (24–32GB) | Everything, including Wan 2.2 and avatars | One-off hardware cost |
| Rented GPU (RunPod / Vast.ai, RTX 4090) | Everything; run `./run.sh` on the pod | ~$0.35–0.70/hour, prices vary |

## Honest limits
- Open video models are good for B-roll but still behind Kling and Veo for complex human motion. Use paid credits only for hero shots.
- The "body clone" here is lip-sync on your real footage, not a fully generated full-body avatar. Open full-body avatar models aren't production-quality yet.
- There is no YouTube downloader, on purpose. It breaks YouTube's terms, and Content ID claims can demonetise your channels. Use the Stock tab, or YouTube Studio's Audio Library for music.
- Only clone voices and faces you own or have written permission to use.

## Files
`server.py` API + job queue · `engines.py` models · `longform.py` assembler · `stock.py` stock search · `static/index.html` UI

Test without downloading any models: `STUDIO_FAKE=1 python server.py`
