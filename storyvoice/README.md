# 🎧 StoryVoice

**Find it · script it · listen to it.** This is a personal app that:

1. **Downloads PDFs from the internet.** You can search free public-domain libraries (Internet Archive and Project Gutenberg), paste any web page to list every PDF on it, paste a direct `.pdf` link, or upload your own file.
2. **Turns videos into scripts.** It works with YouTube, Vimeo, Instagram and 1000+ other sites (via yt-dlp), or with an uploaded video or audio file. It uses the video's own captions when they exist, which is instant. Otherwise it runs AI speech recognition (Whisper) on your machine.
3. **Reads any script aloud** so you can listen instead of reading:
   - **The voice changes with the mood and genre.** Each paragraph is labelled (calm, joyful, sad, suspense, horror, romantic, epic, mystery, inspirational, whimsical, informative). Each mood has its own narrator, speed, pitch and pauses. For example, a children's story uses a bright voice, a horror scene uses a slow, deep male voice, and a motivational passage uses a warm, steady voice.
   - **Background music follows the story.** The music is generated for each mood, so it is royalty-free. It crossfades between scenes and automatically gets quieter while the narrator speaks.
   - **You can follow along.** The current paragraph is highlighted, and a coloured mood strip lets you jump to any scene. You can also download the result as an MP3.
   - You can choose American, British or Indian English, or Hindi voices, and set the narrator gender, speed and music volume. You can also lock the genre or mood.
   - For long books, pick a page range.

## Run it

```bash
cd storyvoice
pip install -r requirements.txt      # also needs ffmpeg installed
uvicorn app.main:app --port 8000
# open http://localhost:8000
# Windows: after the first install, just double-click start.bat
```

Optional settings:

| Env var | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Uses Claude to detect genre and mood more accurately. Without it, an offline keyword model is used. |
| `STORYVOICE_TTS` | `auto` (default). Uses natural Microsoft neural voices via `edge-tts`, which needs internet. Falls back to `espeak-ng` when offline. |
| `STORYVOICE_WHISPER_MODEL` | `base` (default). Use `small` or `medium` for better transcripts, or `tiny` for speed. |
| `STORYVOICE_DATA` | Where the library and audio files are stored (default `storyvoice/data/`). |

## How it works

| File | Role |
|---|---|
| `app/pdf_finder.py` | Library search, page scanning, safe PDF download (size limit, PDF check, private-network block) and text extraction |
| `app/transcribe.py` | yt-dlp captions, with Whisper transcription as fallback, then formatting into paragraphs |
| `app/mood.py` | Genre and per-paragraph mood detection (Claude or offline keyword model), with smoothing so the voice doesn't flicker |
| `app/tts.py` | Maps each mood to a voice and prosody; uses edge-tts with espeak-ng as fallback |
| `app/music.py` | Music synthesiser for each mood (pads, arpeggios, drones, heartbeat, drums) |
| `app/narrate.py` | Combines voice, mood timeline and music with ffmpeg (music ducks under the voice) into an MP3 |

Tests: `python -m pytest -q tests`

## Please note
- Only download books you have the right to read. The built-in search covers public-domain and openly shared libraries, and the page scanner just collects links that a site already offers.
- Scanned PDFs (images with no text layer) need OCR first, for example with `ocrmypdf`.
