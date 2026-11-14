#!/usr/bin/env bash
# Calm Depths: build an intro for a theme   ./build.sh ocean|rain|fireplace|forest
set -euo pipefail
cd "$(dirname "$0")"
THEME="${1:-ocean}"
mkdir -p "work/$THEME"
python3 template/build_background.py --theme "$THEME"
python3 template/ambience.py "$THEME" 45 "work/$THEME/ambience.wav"
python3 template/render_intro.py --theme "$THEME"
echo "Done: exports/CalmDepths_Intro_${THEME}.mp4"
