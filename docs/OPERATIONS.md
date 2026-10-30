# Local operations

## Prerequisites

- Python 3.11
- Node 20+ (Node 24 tested)
- Docker Desktop (optional — simulation mode works without it)
- Ollama (optional — fallback diagnosis works without it)

## First-time setup

```bash
cp .env.example .env
pip install pre-commit && pre-commit install
```

Never commit `.env`. Confirm it is ignored:

```bash
git check-ignore -v .env
```

## Running everything

Use three terminals.

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn app:app --reload --port 8090
```

Backend creates `backend/data/chaos.db` for experiments and samples. The older
`core` scaffold uses `backend/data/chaospilot.db` and
`backend/models/anomaly_detector.pkl`; both directories are git-ignored.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite serves <http://localhost:5173> and proxies `/topology`, `/experiments`,
`/health` and `/ws` to the backend on `127.0.0.1:8090`. Start the backend
first; the dashboard shows the link state and keeps retrying when it is down.

To explore the dashboard without a backend (or while Docker is unavailable),
open <http://localhost:5173/?mock=1>. Mock mode replays a compressed scripted
experiment using the same event shapes as the live stream.

### Sample stack

```bash
cd sample-stack
docker compose up --build
```

Services: gateway `:8000` (public), auth `:8001`, orders `:8002`, cache
`:8003`, payments `:8004`, db `:8005`. Only the gateway is meant for users;
the other ports let the collector reach each service directly.

## Useful commands

```bash
# API health and topology
curl http://localhost:8090/health
curl http://localhost:8090/topology

# Run a 10s baseline / 20s fault / 10s recovery experiment
curl -X POST http://localhost:8090/experiments/run \
  -H "Content-Type: application/json" \
  -d '{"fault":"latency","target":"payments","fixes":false}'

# Same, but restart the stack with RESILIENT=true first
curl -X POST http://localhost:8090/experiments/run \
  -H "Content-Type: application/json" \
  -d '{"fault":"memory","target":"db","fixes":true}'

# History and one experiment with samples/postmortem
curl http://localhost:8090/experiments
curl http://localhost:8090/experiments/1

# Watch the live WebSocket stream (starts an experiment unless --no-run)
cd backend
python scripts/ws_client.py --fault latency --target payments
```


## Tests and checks

```bash
cd backend && pytest -q
cd frontend && npm run build
pre-commit run --all-files
```

## Phase 3 API and live stream

`uvicorn app:app --port 8090` serves the Phase 3 API. A run is always
**10 s baseline → 20 s fault → 10 s recovery**, stores labelled samples in
`backend/data/chaos.db`, and broadcasts `state`, `metrics`, `score`, `log` and
`postmortem` events on `ws://127.0.0.1:8090/ws`. Only one experiment can run at
a time. See [`API.md`](API.md) for response shapes.

```bash
cd backend
python scripts/ws_client.py --fault latency --target payments
# or observe without starting a run:
python scripts/ws_client.py --no-run
```

`fixes=true` restarts the sample stack through Docker Compose with
`RESILIENT=true`; `fixes=false` uses the stack as it is.

## Phase 2 harness (standalone collector)

`backend/collector.py`, `backend/db.py` and `backend/chaos/engine.py` are
independent of the FastAPI app, so they can be exercised without Docker:

```bash
# sample stack must already be running (compose or local Uvicorn processes)
cd backend
python scripts/smoke_test.py
```

The smoke test starts the 1-second collector, records a baseline, injects
2000 ms of latency on `payments` for 10 seconds, resets every service and
records recovery. It prints gateway `/checkout` p50 before/during/after, writes
`backend/data/smoke.db` and exits non-zero unless the gateway p50 jumps by at
least 800 ms. Useful flags: `--fault-ms`, `--duration`, `--target`, `--host`,
`--db`, `--min-jump-ms`.

`ChaosEngine` reads `SAMPLE_STACK_HOST` (default `127.0.0.1`) and
`COMPOSE_PROJECT_NAME` (default `chaospilot`). Latency, memory and reset are
HTTP calls to `/_chaos/*`; only `kill`/`restore` need the Docker daemon.

## Stack control and Docker

The Phase 3 API controls the sample stack directly:

- `latency`, `memory` and `reset` are HTTP calls to `/_chaos/*`.
- `kill` and `restore` use the Docker SDK for Python and need a running Docker
  daemon plus the `chaospilot` Compose project.
- `fixes=true` runs `docker compose up -d --force-recreate` in
  `sample-stack/` with `RESILIENT=true` in the environment, which recreates the
  containers with the resilient profile.

Without Docker, latency and memory experiments still work against the stack if
its services are reachable on ports 8000–8005. `kill`/`restore` and
`fixes=true` return a clear error in the live log and postmortem instead of
crashing the API.

## Enabling the LLM

Default (local, no key):

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```

Hosted OpenAI-compatible endpoint:

```dotenv
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=...     # real value only in .env, never in git
```

The key stays in the backend process. The frontend never sees it.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Dashboard empty | Backend running? `GET /health` |
| No anomalies | Wait for ~30 samples or call `/api/anomalies/train` |
| Agent says `fallback` | Ollama down or no API key; expected offline |
| Faults not applied | `CHAOSPILOT_DOCKER_ENABLED=true`, compose project running |
| CORS error | Match `CHAOSPILOT_CORS_ORIGINS` to the Vite origin |
| Hook cannot build gitleaks | Install Go 1.22+ or use `pre-commit` with the Docker hook |

## Data reset

```bash
rm -rf backend/data backend/models
```

Both directories are recreated on the next backend start.
