# AGENTS.md

Guidance for AI agents and humans working in this repository.

## 1. Project goal

**ChaosPilot** is an AI agent for chaos engineering on a small microservices
stack. It closes the loop between *breaking things on purpose* and *explaining
what happened*:

1. **Collect real-world data** from keyless public APIs (statuspage incident
   feeds, GitHub events, Open-Meteo weather) via a backend data agent.
2. **Simulate faults in-process** (latency, kill, memory) across six services
   (gateway, auth, orders, payments, cache, db) with a deterministic simulator.
3. **Detect anomalies** with an ML model (Isolation Forest, with a statistical
   fallback) instead of fixed thresholds alone.
4. **Explain failures and fixes** using an LLM agent that receives the anomaly
   context, recent metrics and injected-fault timeline as grounded evidence.
5. **Show everything** in a React dashboard: service topology, live charts,
   anomaly feed and the agent's incident report.

The system is a *lab*, not a production chaos platform. There is **no Docker**:
the microservices are an in-process simulator under `backend/sim/`, deterministic
when given a seed.

## 2. Repository structure

```text
chaospilot/
├── AGENTS.md                  # This file: goal, rules, conventions
├── README.md                  # Overview, quickstart, security notice
├── .env.example               # Placeholder-only environment template
├── .env                       # Local secrets (gitignored, never committed)
├── .gitignore                 # Secrets, caches, models, node_modules
├── .pre-commit-config.yaml    # gitleaks + local secret guard
├── .gitleaks.toml             # Secret scanning configuration
├── scripts/
│   ├── build_seed.py          # Builds offline seed dataset + trains the model
│   └── check_secrets.py       # Fast staged-file secret guard
├── backend/                   # FastAPI application (all server-side logic)
│   ├── app.py                 # API: topology, scenarios, experiments, /ws
│   ├── api_config.py          # Env-driven settings
│   ├── collector.py           # telemetry collector helpers
│   ├── db.py                  # experiments, samples, scenarios, fetch_log
│   ├── experiments.py         # background simulator experiment runner
│   ├── runtime.py             # status, score, postmortem helpers
│   ├── stack.py               # (kept for reference; no Docker used)
│   ├── topology.py            # simulator service graph
│   ├── ws.py                  # WebSocket fan-out
│   ├── scripts/               # smoke test + WebSocket client
│   ├── sim/                   # in-process chaos simulator (topology, service, simulator)
│   ├── agent/                 # LLM agent + data agent (data_agent.py)
│   ├── ml/                    # Isolation Forest training, detector, features
│   ├── data/seed/             # committed offline seed dataset (incidents, load, metrics)
│   ├── models/                # trained Isolation Forest (gitignored, built by build_seed.py)
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
├── run_demo.sh                # One-command demo (Linux/macOS)
├── run_demo.ps1               # One-command demo (Windows)
└── docs/                      # Architecture, phases, API, security, ops
```

## 3. Rules (non-negotiable)

### Language and code style

- **Python 3.11** for all backend code. Do not use syntax or libraries that
  require a newer runtime.
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
  `python-dotenv` + `pydantic-settings` (`backend/core/config.py`) and the API
  settings (`backend/api_config.py`). Never read secrets with hardcoded
  fallbacks.
- The frontend may only read `import.meta.env.VITE_*` values that are **public
  and non-secret**. Never put an API key in the frontend or in a `VITE_*` var.
- **All LLM calls happen in the backend.** The browser talks only to the
  backend API.
- Tests and docs use obvious placeholders (`your-api-key-here`, `<TOKEN>`).
- Every commit is scanned by **gitleaks** through the pre-commit framework.
  Do not bypass hooks with `--no-verify`.

### Workflow

- **Every phase must run before moving on.** A phase is done only when its
  checks pass locally (backend tests, lint/type checks where applicable,
  frontend build). Never start the next step with a broken step.
- Commit small and often, one logical change per commit.
- New behaviour needs a test. Bug fixes need a regression test.
- Do not add a dependency without a reason documented in the PR/commit.
- Never rewrite `main` history or force-push to `main`.

## 4. Tech stack

| Layer | Technology |
| --- | --- |
| Backend API | FastAPI, Uvicorn, Pydantic v2 |
| Persistence | SQLite (WAL mode, standard library `sqlite3`) |
| ML | scikit-learn (Isolation Forest), NumPy, joblib |
| Simulator | in-process Python (`backend/sim`), deterministic with a seed |
| Chaos faults | kill, latency, memory (simulated; no Docker) |
| LLM | Ollama (default, local) or any OpenAI-compatible API |
| Data agent | httpx (10s timeout, 3 retries, backoff, User-Agent) |
| Frontend | React 18, Vite, TypeScript |
| Styling | Tailwind CSS |
| Topology graph | React Flow (`@xyflow/react`) |
| Charts | Recharts |
| Tooling | pytest, Ruff, pre-commit, gitleaks |

## 5. Phase plan (updated for the Docker-free flow)

| Phase | Scope | Exit criteria |
| --- | --- | --- |
| 0 | Structure, docs, secrets safety, git | `.env` ignored, hooks installed, first commit |
| 1 | In-process simulator | six services, fault propagation, deterministic |
| 2 | Seed dataset + anomaly model | build_seed.py produces 150+ incidents, 2000+ load points, 5000+ metric rows; model trains |
| 3 | Data agent | collects from keyless APIs, cache/seed fallback, never crashes |
| 4 | Simulator experiments | run agent-built scenarios, resilience score, postmortem |
| 5 | Frontend | collect button, scenario list, run button, live dashboard |
| 6 | End-to-end demo | run_demo.sh starts everything with one command |

Full details: [`docs/PHASES.md`](docs/PHASES.md).

## 6. Commands

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
uvicorn app:app --reload --port 8090
pytest -q

# Build the offline seed dataset and train the anomaly model (zero internet)
python scripts/build_seed.py

# Frontend
cd frontend
npm install
npm run dev
npm run build

# One-command demo (no Docker)
./run_demo.sh        # Linux/macOS
.\run_demo.ps1       # Windows

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

## 8. Integrated Skills & Design Memory

### Active Skills (`.agents/skills/`)
- `impeccable`: Design taste, hierarchy, rhythm, anti-slop guidelines ([pbakaus/impeccable](https://github.com/pbakaus/impeccable)).
- `taste-skill`: Visual craft, refined dark mode tokens ([leonxlnx/taste-skill](https://github.com/leonxlnx/taste-skill)).
- `emilkowalski-motion`: Spring physics, micro-interactions ([emilkowalski/skills](https://github.com/emilkowalski/skills)).
- `ui-ux-pro-max`: Bento grids, tactical HUD elements ([nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)).
- `diagram-design`: Architecture diagramming & topology flows ([cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design)).
- `scrapling-harvester`: Resilient statuspage & incident scraping ([D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling)).
- `onyx-rag`: Grounded agent reasoning, citations, postmortems ([onyx-dot-app/onyx](https://github.com/onyx-dot-app/onyx)).
- `hallmark-apps`: Benchmark web application polish ([nutlope/hallmark](https://github.com/nutlope/hallmark)).
- `ponytail-ui`: Modular component tokens ([dietrichgebert/ponytail](https://github.com/dietrichgebert/ponytail)).
- `crab-agent`: Autonomous agent execution loops ([lemonadesaltbagel/crab](https://github.com/lemonadesaltbagel/crab)).
- `stickman-director`: Timeline choreography & incident replay ([kaomei/stickman-video-director](https://github.com/kaomei/stickman-video-director)).
- `ui-anatomy`: Atomic specs and state machines ([wheresryan22/anatomy](https://github.com/wheresryan22/anatomy)).
- `skillspector`: Real-time telemetry inspection ([nvidia/skillspector](https://github.com/nvidia/skillspector)).
- `semgrep-audit`: Static code security, zero secret leaks ([semgrep/semgrep](https://github.com/semgrep/semgrep)).
- `free-dev-resources`: Free/keyless developer telemetry ([ripienaar/free-for-dev](https://github.com/ripienaar/free-for-dev)).

### Design & Interactive Elements Memory
- **Three.js**: Interactive 3D WebGL Holographic Chaos Core, orbital satellite nodes, dynamic wireframe deformation.
- **Componentry** (`componentry.dev/docs`): Interactive UI primitives.
- **Orbs Library** (`libraries.dev/orbs`): Floating interactive 3D WebGL spheres & ambient aura.
- **React Bits** (`reactbits.dev`): SpotlightCard cursor glow, ShinyText, AnimatedCounter.
- **Skiper UI & Vengeance UI** (`skiper-ui.com`, `vengenceui.com`): Cyberpunk dark cockpit styling, radar badges.
- **OriginKit** (`originkit.dev`): Accessible tactical components.
- **Lenis** (`lenis.dev`): Butter-smooth micro-interactions.
