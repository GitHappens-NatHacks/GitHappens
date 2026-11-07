#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

#shellcheck disable=SC1091
source .venv/bin/activate

pyinstaller \
  --name AccessShiftAI \
  --windowed \
  --noconfirm \
  --paths "$ROOT" \
  --add-data "assets:assets" \
  accessshift/__main__.py

echo "Build output under dist/AccessShiftAI"
