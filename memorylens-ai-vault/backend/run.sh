#!/usr/bin/env bash
# Sets up (if needed) and runs the MemoryLens AI backend on :8000.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "Creating virtualenv..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

echo "Starting MemoryLens AI backend on http://localhost:8000 ..."
# --reload-dir app restricts the file-watcher to source code only --
# without it, uvicorn watches the whole backend/ folder including venv/
# (many thousands of files for faster-whisper/opencv/etc.), which makes
# the watcher's startup scan slow and can trigger spurious reload/restart
# cycles whenever a package is installed or updated, briefly dropping
# in-flight requests while the server process restarts.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
