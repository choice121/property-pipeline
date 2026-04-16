#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Layer 1: Load .env into shell environment (before anything else) ──────────
# This ensures ALL vars are exported at the OS process level, not just Python-
# level dotenv. Any child process (uvicorn, vite, scripts) inherits them too.
if [ -f "$APP_DIR/backend/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$APP_DIR/backend/.env"
  set +a
  echo "==> Credentials loaded from backend/.env"
else
  echo "==> WARNING: backend/.env not found — credentials may be missing."
fi

# ── Layer 2: Smart startup validator ─────────────────────────────────────────
# Defines every var the app needs, checks presence, and surfaces exactly what
# is missing so a developer can fix it immediately with zero guesswork.

REQUIRED_VARS=(
  "SUPABASE_URL:Supabase project URL (e.g. https://xxxx.supabase.co)"
  "SUPABASE_SERVICE_ROLE_KEY:Supabase service-role JWT — allows backend read/write access"
)

PUBLISHING_VARS=(
  "IMAGEKIT_PUBLIC_KEY:ImageKit public key — needed to upload listing photos"
  "IMAGEKIT_PRIVATE_KEY:ImageKit private key — needed to upload listing photos"
  "IMAGEKIT_URL_ENDPOINT:ImageKit CDN endpoint (e.g. https://ik.imagekit.io/yourID)"
)

OPTIONAL_VARS=(
  "SUPABASE_ANON_KEY:Supabase anon key — used by the public website"
  "DEEPSEEK_API_KEY:DeepSeek key — enables all AI features (autofill, rewrite, SEO)"
  "CHOICE_LANDLORD_ID:Landlord UUID — optional, auto-resolved from Supabase if absent"
)

MISSING_REQUIRED=()
MISSING_PUBLISHING=()
MISSING_OPTIONAL=()

for entry in "${REQUIRED_VARS[@]}"; do
  key="${entry%%:*}"
  val="${!key:-}"
  if [ -z "$val" ]; then MISSING_REQUIRED+=("$entry"); fi
done

for entry in "${PUBLISHING_VARS[@]}"; do
  key="${entry%%:*}"
  val="${!key:-}"
  if [ -z "$val" ]; then MISSING_PUBLISHING+=("$entry"); fi
done

for entry in "${OPTIONAL_VARS[@]}"; do
  key="${entry%%:*}"
  val="${!key:-}"
  if [ -z "$val" ]; then MISSING_OPTIONAL+=("$entry"); fi
done

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          Property Pipeline — Startup Check               ║"
echo "╠══════════════════════════════════════════════════════════╣"

if [ ${#MISSING_REQUIRED[@]} -eq 0 ]; then
  echo "║  ✔  Core credentials     → OK                            ║"
else
  echo "║  ✘  Core credentials     → MISSING (app will not work)   ║"
  for entry in "${MISSING_REQUIRED[@]}"; do
    key="${entry%%:*}"; desc="${entry#*:}"
    printf "║     %-54s  ║\n" "• $key"
    printf "║       %-52s  ║\n" "$desc"
  done
fi

if [ ${#MISSING_PUBLISHING[@]} -eq 0 ]; then
  echo "║  ✔  Publishing (ImageKit)→ OK                            ║"
else
  echo "║  ⚠  Publishing (ImageKit)→ INCOMPLETE (publish disabled) ║"
  for entry in "${MISSING_PUBLISHING[@]}"; do
    key="${entry%%:*}"
    printf "║     %-54s  ║\n" "• $key"
  done
fi

if [ ${#MISSING_OPTIONAL[@]} -eq 0 ]; then
  echo "║  ✔  Optional features    → All enabled                   ║"
else
  echo "║  ⚠  Optional features    → Some disabled                 ║"
  for entry in "${MISSING_OPTIONAL[@]}"; do
    key="${entry%%:*}"
    printf "║     %-54s  ║\n" "• $key (optional)"
  done
fi

echo "╚══════════════════════════════════════════════════════════╝"
echo ""

if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
  echo "==> FATAL: Required credentials are missing. Add them to backend/.env and restart."
  echo "==> See backend/.env.example for a full template."
  exit 1
fi

# ── Layer 3: Python virtual environment ──────────────────────────────────────
if [ ! -f "$APP_DIR/.venv/bin/python" ]; then
  echo "==> Creating Python virtual environment..."
  python3 -m venv "$APP_DIR/.venv"
fi

echo "==> Installing / verifying Python dependencies..."
"$APP_DIR/.venv/bin/pip" install --no-user -q -r "$APP_DIR/backend/requirements.txt"

# ── Layer 4: Frontend dependencies ───────────────────────────────────────────
if [ ! -d "$APP_DIR/frontend/node_modules" ]; then
  echo "==> Installing frontend dependencies..."
  cd "$APP_DIR/frontend" && npm install --silent
fi

echo "==> All checks passed. Starting services..."
echo ""

pkill -f "vite.*--port 5000" 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true
sleep 1

# ── Start backend ─────────────────────────────────────────────────────────────
cd "$APP_DIR/backend"
"$APP_DIR/.venv/bin/python" main.py &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── Start frontend ────────────────────────────────────────────────────────────
cd "$APP_DIR/frontend"
"$APP_DIR/frontend/node_modules/.bin/vite" --host 0.0.0.0 --port 5000 --strictPort
