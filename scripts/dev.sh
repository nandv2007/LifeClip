#!/usr/bin/env bash
# LifeClip local development: installs dependencies and starts backend+frontend.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Checking system dependencies"
if ! command -v tesseract >/dev/null 2>&1; then
  echo "    Tesseract OCR not found. Install it:"
  echo "      Debian/Ubuntu: sudo apt-get install tesseract-ocr"
  echo "      macOS:         brew install tesseract"
  exit 1
fi

if [ ! -f "$ROOT/backend/.env" ]; then
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
  echo "==> Created backend/.env from .env.example (add your Cloudinary API key + secret)"
fi

echo "==> Installing backend dependencies"
python3 -m pip install --quiet -r "$ROOT/backend/requirements.txt"

echo "==> Installing frontend dependencies"
(cd "$ROOT/frontend" && npm install --no-audit --no-fund --silent)

echo ""
echo "Starting LifeClip:"
echo "  backend  -> http://localhost:8787  (API docs: /api/docs)"
echo "  frontend -> http://localhost:5173"
echo ""

(cd "$ROOT/backend" && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8787) &
BACK_PID=$!
trap 'kill $BACK_PID 2>/dev/null || true' EXIT

sleep 2
(cd "$ROOT/frontend" && npm run dev)
