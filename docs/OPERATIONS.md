# Local operations

## Prerequisites

- Python 3.11+
- Node 20+ (Node 24 tested)
- Ollama (optional — fallback diagnosis works without it)

No Docker is required. The microservices are simulated in-process by
`backend/sim/`.

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

The fastest path from a clean clone is one command, which creates `.env`,
installs dependencies, builds the seed data and trains the anomaly model if
missing, then launches the backend and dashboard:

```bash
./run_demo.sh                                  # macOS / Linux
powershell -ExecutionPolicy Bypass -File .\run_demo.ps1   # Windows
```

The manual two-terminal sequence below is equivalent.

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python scripts/build_seed.py    # builds seed data + trains the model (offline)
uvicorn app:app --reload --port 8090
```

Backend creates `backend/data/chaos.db` for experiments and samples, plus
`backend/data/seed/` (committed) and `backend/models/isolation_forest.joblib`
(git-ignored). The older `core` scaffold uses `backend/data/chaospilot.db`;
both directories are git-ignored.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite serves <http://localhost:5173> and proxies `/topology`, `/experiments`,
`/scenarios`, `/agent`, `/health` and `/ws` to the backend on `127.0.0.1:8090`.
Start the backend first; the dashboard shows the link state and keeps retrying
when it is down.

To explore the dashboard without a backend, open
<http://localhost:5173/?mock=1>. Mock mode replays a compressed scripted
experiment using the same event shapes as the live stream.

## Useful commands

```bash
# API health and topology
curl http://localhost:8090/health
curl http://localhost:8090/topology

# List scenarios built by the data agent
curl http://localhost:8090/scenarios

# Collect real-world data into scenarios (streams progress over WebSocket)
curl -X POST http://localhost:8090/agent/collect

# Run an agent-stored scenario (fixes = resilient / one-hop containment)
curl -X POST http://localhost:8090/experiments/run \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":1,"fixes":false}'

# Same, with resilience fixes on
curl -X POST http://localhost:8090/experiments/run \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":1,"fixes":true}'

# History and one experiment with samples/postmortem
curl http://localhost:8090/experiments
curl http://localhost:8090/experiments/1

# Watch the live WebSocket stream
cd backend
python scripts/ws_client.py
```

An experiment is always **baseline → fault → recovery**, stores labelled samples
in `backend/data/chaos.db`, and broadcasts `state`, `metrics`, `anomaly`,
`score`, `log` and `postmortem` events on `ws://127.0.0.1:8090/ws`. Only one
experiment can run at a time. See [`API.md`](API.md) for response shapes.

## Phase 2 harness (standalone collector)

`backend/collector.py` and `backend/db.py` are independent of the FastAPI app:

```bash
cd backend
python scripts/smoke_test.py
```

The smoke test starts the 1-second collector, records a baseline, injects
2000 ms of latency on `payments` for 10 seconds, resets every service and
records recovery. It prints gateway `/checkout` p50 before/during/after, writes
`backend/data/smoke.db` and exits non-zero unless the gateway p50 jumps by at
least 800 ms. Useful flags: `--fault-ms`, `--duration`, `--target`, `--host`,
`--db`, `--min-jump-ms`.

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
| No scenarios | Call `POST /agent/collect`; falls back to cache/seed offline |
| No anomalies | Wait for ~30 samples; the model retrains if missing |
| Agent says `fallback` | Ollama down or no API key; expected offline |
| CORS error | Match `CHAOSPILOT_CORS_ORIGINS` to the Vite origin |
| Hook cannot build gitleaks | Install Go 1.22+ or use `pre-commit` with the Docker hook |
| Experiment `400` | scenario id not stored by the agent; call `/agent/collect` first |
| Experiment `409` | a run is already in progress |

## Tests and checks

```bash
cd backend && pytest -q
cd frontend && npm run build
pre-commit run --all-files
```

## Data reset

```bash
rm -rf backend/data backend/models
```

Both directories are recreated on the next backend start. `backend/data/seed/`
is committed and restored from git; `backend/models/` and `backend/data/*.db`
are git-ignored and regenerated by `scripts/build_seed.py`.
