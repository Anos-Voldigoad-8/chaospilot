# Phase plan

Every phase must **run and pass its exit criteria before the next one starts**.
This is a repository rule (see `AGENTS.md`).

ChaosPilot is now Docker-free: the microservices are an in-process, deterministic
simulator under `backend/sim/`, and scenarios are built from real-world data by
the backend data agent.

## Phase 0 — Structure, docs, secrets safety

**Deliverables**

- Monorepo folders: `backend/`, `frontend/`, `docs/`, `scripts/`.
- `AGENTS.md`, `README.md`, `.gitignore`, `.env.example`.
- gitleaks pre-commit hook (official hook + local guard).
- Git initialised with the Phase 0 commit.

**Exit criteria**

- [ ] `git check-ignore -v .env` prints the matching `.gitignore` rule.
- [ ] `git status --short` never lists `.env`.
- [ ] `pre-commit run --all-files` passes.
- [ ] No literal credentials in any tracked file.

**Verification**

```bash
git check-ignore -v .env
pre-commit run --all-files
git grep -nE "(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9]{20,}" || true
```

## Phase 1 — In-process simulator

**Deliverables**

- Six simulated services: gateway, auth, orders, payments, cache, db with the
  dependency graph gateway→auth/orders, auth→cache, orders→payments/db,
  payments→db.
- Each service: baseline latency, error rate, load capacity.
- Faults: kill (service down), latency (added ms), memory (degrading capacity).
- `fixes` (resilient) flag simulates retry, timeout, circuit breaker; blast
  radius contained to one hop.
- Deterministic per-second metrics (`latency_ms`, `error_rate`, `up`) given a
  seed; a fault on one service raises latency/errors upstream.

**Exit criteria**

- [ ] `pytest` simulator tests pass: fault on payments raises orders and
  gateway latency; fixes reduce blast radius.
- [ ] Same seed always reproduces identical metrics.

**Verification**

```bash
cd backend && pytest tests/test_simulator.py -q
```

## Phase 2 — Seed dataset + anomaly model

**Deliverables**

- `scripts/build_seed.py` generates `backend/data/seed/`:
  - `incidents_seed.json` — 150+ incident records (component, impact,
    duration minutes, title).
  - `load_seed.csv` — 2000+ hourly request-load points.
  - `metrics_seed.csv` — 5000+ labelled healthy/fault rows from the simulator.
- Train Isolation Forest on healthy windows only; save with joblib.
- Write precision, recall, F1 and confusion matrix to `docs/model_metrics.json`.
- Auto-retrain if the model file is missing at startup.

**Exit criteria**

- [ ] `scripts/build_seed.py` runs offline and produces the three seed files.
- [ ] `docs/model_metrics.json` has real numbers (precision/recall/F1).
- [ ] `pytest tests/test_ml_train.py` passes.

**Verification**

```bash
python scripts/build_seed.py
cd backend && pytest tests/test_ml_train.py -q
python -c "import json; m=json.load(open('docs/model_metrics.json')); print(m['test']['f1'])"
```

## Phase 3 — Data agent (internet → scenarios)

**Deliverables**

- `backend/agent/data_agent.py` collects from keyless public APIs:
  - Statuspage incident feeds (`/api/v2/incidents.json`).
  - GitHub public events (traffic load signal).
  - Open-Meteo hourly forecast (weather load signal).
- LLM picks sources and parameters, validated with pydantic; seeded random
  picker after two LLM failures.
- httpx with 10s timeout, 3 retries + backoff, User-Agent header.
- Raw responses cached in `backend/data/cache/`; fallback chain live → cache →
  seed; never crashes on network problems.
- Converts raw data into scenarios (fault type, target service, duration,
  severity, load curve); persists scenarios + fetch log to SQLite.

**Exit criteria**

- [ ] `pytest tests/test_agent_data.py` passes (mapper, scenario conversion,
  fallback chain with network down).
- [ ] With internet on, at least one scenario is marked `live`.
- [ ] With internet off, `POST /agent/collect` still yields scenarios.

**Verification**

```bash
cd backend && pytest tests/test_agent_data.py -q
```

## Phase 4 — Simulator experiments

**Deliverables**

- `POST /agent/collect` runs the data agent, streams progress over WebSocket.
- `GET /scenarios` lists scenarios (title, source, target, severity).
- `POST /experiments/run {scenario_id, fixes}` — an experiment can **only**
  run a scenario stored by the agent; no hardcoded/manual fault selection.
- Simulator drives the experiment; resilience score, anomaly score, postmortem
  that uses the real incident title and source.

**Exit criteria**

- [ ] `pytest tests/test_sim_api.py` passes (collect, scenario-only runs,
  unknown scenario rejected).
- [ ] Fixes reduce blast radius (higher resilience score).
- [ ] Postmortem references the scenario title and source.

**Verification**

```bash
cd backend && pytest tests/test_sim_api.py -q
```

## Phase 5 — Frontend dashboard

**Deliverables**

- React + Vite + TypeScript + Tailwind HUD shell.
- React Flow service map with health colouring and failure propagation.
- Recharts live metrics and anomaly stream.
- `COLLECT DATA` button showing live agent log lines and source used
  (live/cached/seed).
- Scenario list with title, source, target, severity and a "Data source" badge
  (LIVE / CACHED / SEED) plus the real source URL.
- `RUN` button for a chosen scenario; `Apply fixes` toggle.
- Postmortem panel, anomaly score, resilience score, compare panel.
- Loading, empty and backend-unreachable states; `?mock=1` still works.

**Exit criteria**

- [ ] `npm run build` passes (TypeScript strict + Vite).
- [ ] No fault/target pickers remain; only scenario selection.
- [ ] Data-source badge shown per scenario with the source URL.

**Verification**

```bash
cd frontend && npm run build
```

## Phase 6 — End-to-end demo

**Deliverables**

- `run_demo.sh` and `run_demo.ps1`: one command installs dependencies, builds
  seed data + model if missing, starts backend + frontend.
- Demo works with zero internet (seed data + model committed).
- With internet, at least one scenario marked `live`.

**Exit criteria**

- [ ] `./run_demo.sh` (or `.\run_demo.ps1`) starts a clean clone end to end.
- [ ] Backend tests, frontend build, pre-commit all pass.
- [ ] `git status` never lists `.env`.
