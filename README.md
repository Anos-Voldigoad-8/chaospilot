# ChaosPilot

**ChaosPilot is an AI agent that breaks your microservices on purpose, notices
when they misbehave, and explains why — with fix suggestions grounded in the
telemetry it collected.**

It combines chaos engineering, ML anomaly detection and an LLM incident analyst
in one small, self-hosted lab.

```text
        inject faults            collect telemetry          detect anomalies
 ┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
 │   Chaos engine   │───────▶│ 5 FastAPI svcs   │───────▶│  Collector + DB  │
 │ (Docker SDK)     │        │  (sample stack)  │        │  (SQLite)        │
 └──────────────────┘        └──────────────────┘        └────────┬─────────┘
            ▲                                                     │
            │            ┌──────────────────┐                     ▼
            └────────────│   LLM agent      │◀─────────── Isolation Forest
                         │ explain + fix    │             (scikit-learn)
                         └────────┬─────────┘
                                  ▼
                         React dashboard (React Flow, Recharts)
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `sample-stack/` | Docker Compose stack with a gateway and five small FastAPI services |
| `backend/` | FastAPI app: chaos engine, collector, ML, LLM agent, API |
| `backend/ml/` | Phase 5 dataset generator, window features, Isolation Forest and detector |
| `backend/agent/` | Phase 6 tools, LLM planner, postmortem writer and live step logs |
| `frontend/` | React + Vite + Tailwind dashboard |
| `docs/` | Architecture, phases, API reference, security and operations |

## Quickstart

```bash
# 1. Environment (never commit .env)
cp .env.example .env            # Windows: Copy-Item .env.example .env
# edit .env, then install the secret-scanning hook
pip install pre-commit
pre-commit install

# 2. Backend
cd backend
python -m venv .venv
.venv/Scripts/activate           # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn app:app --reload --port 8090

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev

# 4. Sample stack (new terminal, requires Docker Desktop)
cd sample-stack
docker compose up --build
```

Open <http://localhost:5173>. API docs live at <http://localhost:8090/docs>.

The dashboard streams the service map, resilience score and telemetry over
`/ws`. Without a backend (or Docker), open
<http://localhost:5173/?mock=1> to replay a scripted experiment.

ChaosPilot starts in **simulation mode** (`CHAOSPILOT_SIMULATION_MODE=true`),
so you can explore the dashboard, anomaly detection and the agent without
Docker or an LLM. Set `CHAOSPILOT_DOCKER_ENABLED=true` to inject real faults,
and configure Ollama (or an OpenAI-compatible key) for live LLM analysis.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Phase plan](docs/PHASES.md)
- [Anomaly model pipeline](backend/ml/README.md)
- [Agent planner and postmortem](backend/agent/README.md)
- [API reference](docs/API.md)
- [Security policy](docs/SECURITY.md)
- [Local operations](docs/OPERATIONS.md)

## SECURITY — read before contributing

> **This repository is public. Never commit credentials.**
>
> 1. Copy `.env.example` to `.env` and fill in your own values. `.env` is
>    git-ignored and must never appear in `git status`.
> 2. All backend configuration/secrets are loaded from environment variables
>    with `python-dotenv` and `pydantic-settings`. There are no hardcoded keys.
> 3. The frontend only receives non-secret `VITE_*` values. **LLM API keys
>    never enter the browser**; every LLM call is made by the backend.
> 4. `docker-compose.yml` uses `env_file` / `${VAR}` references only.
> 5. A **gitleaks** pre-commit hook blocks commits containing secrets. Install
>    it once with `pre-commit install`. Do not use `git commit --no-verify`.
>
> If a secret is ever pushed: rotate it immediately, then purge it from
> history. Removing it in a later commit is not enough.

Verify `.env` is ignored:

```bash
git check-ignore -v .env
# .gitignore:5:.env	.env
```

See [docs/SECURITY.md](docs/SECURITY.md) for the full policy.

## License

MIT — see `LICENSE`.
