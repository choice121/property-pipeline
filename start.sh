#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Checking environment setup..."

# ── Python virtual environment ─────────────────────────────────────────────
if [ ! -f "$APP_DIR/.venv/bin/python" ]; then
  echo "==> Creating Python virtual environment..."
  python3 -m venv "$APP_DIR/.venv"
fi

echo "==> Installing / verifying Python dependencies..."
"$APP_DIR/.venv/bin/pip" install --no-user -q -r "$APP_DIR/backend/requirements.txt"

# ── Frontend node_modules ──────────────────────────────────────────────────
if [ ! -d "$APP_DIR/frontend/node_modules" ]; then
  echo "==> Installing frontend dependencies..."
  cd "$APP_DIR/frontend" && npm install --silent
fi

echo "==> Environment ready. Starting services..."

# ── Start backend ──────────────────────────────────────────────────────────
cd "$APP_DIR/backend"
"$APP_DIR/.venv/bin/python" main.py &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── Start frontend ─────────────────────────────────────────────────────────
cd "$APP_DIR/frontend"
"$APP_DIR/frontend/node_modules/.bin/vite" --host 0.0.0.0 --port 5000 --strictPort
