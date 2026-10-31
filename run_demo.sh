#!/usr/bin/env bash
# ChaosPilot one-command demo: sample stack + backend + dashboard.
#
#   ./run_demo.sh
#
# Requirements: Docker with Compose v2, Python 3.11, Node.js 18+.
# The script is safe to re-run: it only creates .env, the virtualenv and
# node_modules when they are missing. The dashboard runs in the foreground;
# Ctrl+C stops the backend and leaves the sample stack running (stop it with
# `docker compose -f sample-stack/docker-compose.yml down`).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

say() { printf '\n\033[36m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "Docker is required: https://docs.docker.com/get-docker/"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required (docker compose)."

if [ ! -f .env ]; then
  cp .env.example .env
  say "created .env from .env.example (edit it to use Ollama or OpenAI)"
fi

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || fail "python3 was not found; set PYTHON=/path/to/python3.11"

if [ ! -x backend/.venv/bin/python ]; then
  say "creating backend virtualenv"
  "$PYTHON" -m venv backend/.venv
fi

VENV_PY="$ROOT/backend/.venv/bin/python"
say "installing backend dependencies"
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r backend/requirements.txt

if [ ! -d frontend/node_modules ]; then
  say "installing frontend dependencies"
  (cd frontend && npm install)
fi

health_check() {
  "$VENV_PY" - "$1" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
}

wait_for() {
  local url="$1" label="$2" attempts="${3:-120}"
  for _ in $(seq 1 "$attempts"); do
    if health_check "$url"; then return 0; fi
    sleep 1
  done
  fail "$label did not become healthy at $url"
}

say "starting the sample stack"
docker compose -f sample-stack/docker-compose.yml up -d --build
wait_for "http://127.0.0.1:8000/health" "sample-stack gateway"

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

say "dashboard: http://localhost:5173   API docs: http://127.0.0.1:8090/docs"
(cd frontend && npm run dev)
