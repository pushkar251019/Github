import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("STORYVOICE_DATA", BASE_DIR / "data"))
LIBRARY_DIR = DATA_DIR / "library"
AUDIO_DIR = DATA_DIR / "audio"
TMP_DIR = DATA_DIR / "tmp"
for d in (LIBRARY_DIR, AUDIO_DIR, TMP_DIR):
    d.mkdir(parents=True, exist_ok=True)

MAX_PDF_BYTES = int(os.environ.get("STORYVOICE_MAX_PDF_MB", "150")) * 1024 * 1024
WHISPER_MODEL = os.environ.get("STORYVOICE_WHISPER_MODEL", "base")
# "edge" (natural neural voices, needs internet) or "espeak" (offline, robotic)
TTS_ENGINE = os.environ.get("STORYVOICE_TTS", "auto")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("STORYVOICE_CLAUDE_MODEL", "claude-haiku-5-5")
USER_AGENT = "StoryVoice/1.0 (+personal reading app)"
