#!/usr/bin/env bash
# ChaosPilot one-command demo: simulator + backend + dashboard.
#
#   ./run_demo.sh
#
# Requirements: Python 3.11+, Node.js 20+. No Docker required.
# The script is safe to re-run: it only creates .env, the virtualenv and
# node_modules when they are missing. It builds the seed dataset and trains
# the anomaly model if they are absent, so the app works with zero internet.
# The dashboard runs in the foreground; Ctrl+C stops the backend.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

say() { printf '\n\033[36m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

command -v python >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1 ||
  fail "Python 3.11+ was not found; set PYTHON=/path/to/python3.11"

PYTHON="${PYTHON:-python}"
command -v "$PYTHON" >/dev/null 2>&1 || fail "python was not found"

# --- .env -------------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  say "created .env from .env.example"
fi

# --- backend virtualenv + dependencies --------------------------------------
VENV="$ROOT/backend/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  say "creating backend virtualenv"
  "$PYTHON" -m venv "$VENV"
fi

VENV_PY="$VENV/bin/python"
say "installing backend dependencies"
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r backend/requirements.txt

# --- seed data + anomaly model (offline, zero internet) --------------------
SEED_MARKER="$ROOT/backend/data/seed/metrics_seed.csv"
MODEL_MARKER="$ROOT/backend/models/isolation_forest.joblib"
if [ ! -f "$SEED_MARKER" ] || [ ! -f "$MODEL_MARKER" ]; then
  say "building seed dataset and training the anomaly model"
  "$VENV_PY" "$ROOT/scripts/build_seed.py"
fi

# --- frontend dependencies --------------------------------------------------
NODE_ROOT="$ROOT/frontend"
if [ ! -d "$NODE_ROOT/node_modules" ]; then
  say "installing frontend dependencies"
  (cd "$NODE_ROOT" && npm install --quiet)
fi

# --- health check helper ----------------------------------------------------
health_check() {
  "$VENV_PY" - "$1" <<'PY' >/dev/null 2>&1
import sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
}

wait_for() {
  local url="$1" label="$2" attempts="${3:-60}"
  for _ in $(seq 1 "$attempts"); do
    if health_check "$url"; then return 0; fi
    sleep 1
  done
  fail "$label did not become healthy at $url"
}

# --- start backend ----------------------------------------------------------
say "starting the backend on http://127.0.0.1:8090"
(cd backend && "$VENV_PY" -m uvicorn app:app --host 127.0.0.1 --port 8090) &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  fail "the backend exited during startup; check the log above"
fi
wait_for "http://127.0.0.1:8090/health" "ChaosPilot API" 60

# --- start frontend ---------------------------------------------------------
say "starting the dashboard on http://localhost:5173"
(cd frontend && npm run dev) &
FRONTEND_PID=$!
trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true' EXIT INT TERM

wait_for "http://localhost:5173" "dashboard" 60

say "dashboard: http://localhost:5173   API docs: http://127.0.0.1:8090/docs"
say "Press Ctrl+C to stop the backend and dashboard."
wait
