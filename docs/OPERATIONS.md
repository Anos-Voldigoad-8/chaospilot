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
uvicorn app.main:app --reload --port 8000
```

Backend creates `backend/data/chaospilot.db` and, after enough samples,
`backend/models/anomaly_detector.pkl`. Both are git-ignored.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite serves <http://localhost:5173> and proxies `/api` + `/health` to the
backend.

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
# Capabilities
curl http://localhost:8000/health

# Overview snapshot
curl http://localhost:8000/api/overview

# Train the model
curl -X POST http://localhost:8000/api/anomalies/train

# Inject latency on payments for 2 minutes
curl -X POST http://localhost:8000/api/faults \
  -H "Content-Type: application/json" \
  -d '{"service_id":"payments","fault_type":"latency","duration_seconds":120,"parameters":{"latency_ms":1500}}'

# Ask the agent
curl -X POST http://localhost:8000/api/agent/diagnose \
  -H "Content-Type: application/json" \
  -d '{"service_id":"payments"}'
```

## Tests and checks

```bash
cd backend && pytest -q
cd frontend && npm run build
pre-commit run --all-files
```

## Enabling real chaos

1. Start Docker Desktop and the sample stack.
2. Set in `.env`:

   ```dotenv
   CHAOSPILOT_DOCKER_ENABLED=true
   CHAOSPILOT_SIMULATION_MODE=false
   ```

3. Restart the backend. It discovers containers by the Compose labels
   `com.docker.compose.project=chaospilot` and
   `com.docker.compose.service=<service>`.

If the daemon is unreachable the manager logs a warning and continues in
simulation mode; the API never crashes because Docker is missing.

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
