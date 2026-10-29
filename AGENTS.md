# AGENTS.md

Guidance for AI agents and humans working in this repository.

## 1. Project goal

**ChaosPilot** is an AI agent for chaos engineering on a small microservices
stack. It closes the loop between *breaking things on purpose* and *explaining
what happened*:

1. **Inject faults** into a running Docker Compose stack (latency, errors,
   crashes, resource pressure, network partitions).
2. **Collect telemetry** continuously from every service (health, latency,
   error rate, CPU, memory).
3. **Detect anomalies** with an ML model (Isolation Forest, with a statistical
   fallback) instead of fixed thresholds alone.
4. **Explain failures and fixes** using an LLM agent that receives the anomaly
   context, recent metrics and injected-fault timeline as grounded evidence.
5. **Show everything** in a React dashboard: service topology, live charts,
   anomaly feed and the agent's incident report.

The system is a *lab*, not a production chaos platform. The sample stack is
deliberately small enough to run on a laptop and to make demo failures obvious.

## 2. Repository structure

```text
chaospilot/
├── AGENTS.md                  # This file: goal, rules, conventions
├── README.md                  # Overview, quickstart, security notice
├── .env.example               # Placeholder-only environment template
├── .gitignore                 # Secrets, caches, models, node_modules
├── .pre-commit-config.yaml    # gitleaks + local secret guard
├── .gitleaks.toml             # Secret scanning configuration
├── scripts/
│   └── check_secrets.py       # Fast staged-file secret guard
├── sample-stack/              # Docker Compose demo system (5 FastAPI services)
│   ├── docker-compose.yml
│   ├── README.md
│   └── services/
│       ├── gateway/           # public entry point: GET /checkout
│       ├── auth/              # GET /verify -> cache
│       ├── orders/            # POST /create -> payments, db
│       ├── cache/             # in-memory session cache
│       ├── payments/          # POST /charge -> db
│       └── db/                # in-memory records
├── backend/                   # FastAPI application (all server-side logic)
│   ├── app/
│   │   ├── main.py            # App factory, lifespan, routers
│   │   ├── config.py          # Env-driven settings (python-dotenv)
│   │   ├── database.py        # SQLite connection + schema
│   │   ├── chaos/             # Fault definitions + Docker engine
│   │   ├── collector/         # Telemetry polling and persistence
│   │   ├── ml/                # Features, anomaly model, training
│   │   ├── agent/             # LLM client, prompts, diagnosis agent
│   │   ├── api/               # HTTP routes and schemas
│   │   └── services/          # Domain/store helpers
│   ├── chaos/                 # Phase 2 fault engine (Docker + HTTP)
│   ├── collector.py           # 1s telemetry collector
│   ├── db.py                  # experiments + samples (SQLite)
│   ├── scripts/smoke_test.py  # end-to-end latency-jump smoke test
│   ├── tests/                 # pytest suite (no live secrets required)
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/                  # React + Vite + TypeScript + Tailwind UI
│   ├── src/
│   │   ├── components/        # Topology, charts, tables, agent panel
│   │   ├── hooks/             # Data fetching / live updates
│   │   ├── lib/               # Typed API client
│   │   └── types/             # Shared API types
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
└── docs/                      # Architecture, phases, API, security, ops
```

## 3. Rules (non-negotiable)

### Language and code style

- **Python 3.11** for all backend and sample-stack code. Do not use syntax or
  libraries that require a newer runtime.
- **Type hints everywhere** in Python (`from __future__ import annotations` at
  the top of modules). Public functions need typed parameters and returns.
- **Small files, single responsibility.** Prefer modules under ~250 lines and
  functions under ~40 lines. If a file grows past that, split it.
- Frontend is **TypeScript** (strict mode), functional components and hooks.
- Keep comments about *why*, not *what*. No commented-out code.

### Secrets safety (this repository is PUBLIC)

- **Never commit secrets.** No API keys, tokens, passwords, private keys,
  connection strings with credentials, or real `.env` files.
- All backend secrets/config are read from environment variables through
  `python-dotenv` + `pydantic-settings` (`app/config.py`). Never read secrets
  with hardcoded fallbacks.
- The frontend may only read `import.meta.env.VITE_*` values that are **public
  and non-secret**. Never put an API key in the frontend or in a `VITE_*` var.
- **All LLM calls happen in the backend.** The browser talks only to the
  backend API.
- `docker-compose.yml` uses `env_file: ../.env` and `${VAR}` references only —
  never literal credentials.
- Tests and docs use obvious placeholders (`your-api-key-here`, `<TOKEN>`).
- Every commit is scanned by **gitleaks** through the pre-commit framework.
  Do not bypass hooks with `--no-verify`.

### Workflow

- **Every phase must run before moving on.** A phase is done only when its
  checks pass locally (backend tests, lint/type checks where applicable,
  frontend build, compose config validation). Never start Phase *N+1* with a
  broken Phase *N*.
- Commit small and often, one logical change per commit. Use the phase name in
  the subject (e.g. `Phase 2: anomaly detector`).
- New behaviour needs a test. Bug fixes need a regression test.
- Do not add a dependency without a reason documented in the PR/commit.
- Never rewrite `main` history or force-push to `main`.

## 4. Tech stack

| Layer | Technology |
| --- | --- |
| Backend API | FastAPI, Uvicorn, Pydantic v2 |
| Persistence | SQLite (WAL mode, standard library `sqlite3`) |
| ML | scikit-learn (Isolation Forest), NumPy |
| Chaos / Docker | Docker SDK for Python |
| LLM | Ollama (default, local) or any OpenAI-compatible API |
| Frontend | React 18, Vite, TypeScript |
| Styling | Tailwind CSS |
| Topology graph | React Flow (`@xyflow/react`) |
| Charts | Recharts |
| Tooling | pytest, Ruff, pre-commit, gitleaks |

## 5. Phase plan

| Phase | Scope | Exit criteria |
| --- | --- | --- |
| 0 | Structure, docs, secrets safety, git | `.env` ignored, hooks installed, first commit |
| 1 | Sample stack + collector | 6 services healthy, metrics persisted |
| 2 | Anomaly detection | model trains, detects injected faults |
| 3 | Chaos engine | inject/recover latency, error, crash |
| 4 | LLM agent | grounded diagnosis + fix suggestions |
| 5 | Frontend | topology, charts, incident reports live |
| 6 | End-to-end demo | one command reproduces a full incident |

Full details: [`docs/PHASES.md`](docs/PHASES.md).

## 6. Commands

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest -q

# Frontend
cd frontend
npm install
npm run dev
npm run build

# Sample stack (requires Docker)
cd sample-stack
docker compose config
docker compose up --build

# Secrets safety
pre-commit install
pre-commit run --all-files
git check-ignore -v .env
```

## 7. Definition of done for any change

- [ ] Runs locally with no secrets committed.
- [ ] Python 3.11 compatible, fully type-hinted, files remain small.
- [ ] Tests pass and cover the new behaviour.
- [ ] Frontend build passes when the frontend changed.
- [ ] `pre-commit run --all-files` passes.
- [ ] Docs updated if behaviour or configuration changed.
