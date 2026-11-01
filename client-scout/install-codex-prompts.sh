#!/usr/bin/env sh
# Installs Client Scout slash prompts for Codex CLI (~/.codex/prompts). Usage: ./install-codex-prompts.sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="${CODEX_HOME:-$HOME/.codex}/prompts"
mkdir -p "$DEST"
for f in "$DIR"/.claude/commands/*.md; do
  name=$(basename "$f")
  # Same format ($ARGUMENTS, description/argument-hint frontmatter). Run Codex from the repo root.
  cp "$f" "$DEST/$name"
  echo "installed /${name%.md}"
done
echo "Done. Start Codex inside $DIR and type /scout-setup"
