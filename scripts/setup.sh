#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

# mediapipe==0.10.21 (needed for mp.solutions.face_mesh) has no wheels for Python 3.13+.
PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  for candidate in python3.12 python3.11 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON="$candidate"
      break
    fi
  done
fi
if [[ -z "$PYTHON" ]]; then
  echo "Python 3.10-3.12 is required (3.13+ breaks MediaPipe). Install Python 3.12 from python.org,"
  echo "or point to one: PYTHON=/path/to/python3.12 ./scripts/setup.sh"
  exit 1
fi
echo "Using $("$PYTHON" --version) at $(command -v "$PYTHON")"

"$PYTHON" -m venv .venv
#shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup complete. Activate with: source .venv/bin/activate"
echo "Run with: python -m accessshift"
