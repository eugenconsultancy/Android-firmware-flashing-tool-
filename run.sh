#!/usr/bin/env bash
# Android Flasher — launch script (Linux / macOS / Git Bash)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if present.
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/Scripts/activate
fi

exec python app.py "$@"
