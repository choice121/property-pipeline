#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$APP_DIR/backend"
"$APP_DIR/.venv/bin/python" main.py &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$APP_DIR/frontend"
"$APP_DIR/frontend/node_modules/.bin/vite" --host 0.0.0.0 --port 5000 --strictPort
