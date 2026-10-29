# Phase plan

Every phase must **run and pass its exit criteria before the next one starts**.
This is a repository rule (see `AGENTS.md`).

## Phase 0 — Structure, docs, secrets safety

**Deliverables**

- Monorepo folders: `sample-stack/`, `backend/`, `frontend/`, `docs/`.
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

## Phase 1 — Sample stack and telemetry collector

**Deliverables**

- Five FastAPI services (catalog, cart, checkout, payments, notifications),
  each with `/health`, `/metrics`, `/work`, `/admin/fault`, `/admin/reset`.
- Docker Compose wiring, health checks and dependency URLs.
- Backend collector: polling loop, SQLite persistence, simulation fallback.
- `/api/services`, `/api/metrics`, `/api/overview`.

**Exit criteria**

- [ ] `docker compose config` is valid.
- [ ] `docker compose up --build` shows 5 healthy services.
- [ ] Collector writes one row per service per interval.
- [ ] Overview endpoint returns services and series.

**Verification**

```bash
cd sample-stack && docker compose config
cd backend && pytest tests/test_collector.py -q
curl http://localhost:8000/api/overview
```

## Phase 2 — ML anomaly detection

**Deliverables**

- Feature extraction, IsolationForest detector, statistical fallback.
- Training + persistence in `backend/models/` (git-ignored).
- Detection on every collector tick, anomaly de-duplication.
- `/api/anomalies`, `/api/anomalies/train`, `/api/anomalies/detect`.

**Exit criteria**

- [ ] Detector trains on ≥30 samples per service.
- [ ] An injected latency/error fault produces an anomaly within two ticks.
- [ ] Model artifact is not tracked by git.
- [ ] Detector unit tests pass.

## Phase 3 — Chaos engine

**Deliverables**

- Fault types: latency, error, crash, cpu, memory, network.
- Docker SDK engine with idempotent apply/recover.
- Simulation engine for Docker-less environments.
- Fault lifecycle (`active` → `recovered`/`expired`) and API.

**Exit criteria**

- [ ] Injected fault is visible in metrics within two collector ticks.
- [ ] Recovery restores the baseline within two ticks.
- [ ] Docker-unavailable path degrades to simulation with a warning.
- [ ] Chaos tests pass without a live Docker daemon.

## Phase 4 — LLM incident agent

**Deliverables**

- Ollama + OpenAI-compatible clients, all backend-only.
- Grounded prompt with metrics, anomalies, faults and dependencies.
- Strict JSON parsing, deterministic fallback, incident persistence.
- `/api/agent/status`, `/api/agent/diagnose`, `/api/incidents`.

**Exit criteria**

- [ ] With Ollama running, diagnosis returns a valid report.
- [ ] With LLM disabled, fallback report is still returned and stored.
- [ ] No key appears in any response, log or frontend bundle.
- [ ] Agent tests pass offline.

## Phase 5 — Frontend dashboard

**Deliverables**

- React + Vite + TypeScript + Tailwind shell.
- React Flow topology with health colouring.
- Recharts metrics chart per service.
- Anomaly feed, fault injection panel, incident/agent drawer.

**Exit criteria**

- [ ] `npm run build` succeeds.
- [ ] Dashboard renders simulated data with the backend running.
- [ ] Fault injection round-trip works from the UI.
- [ ] Bundle contains no secret (`npm run build` + grep).

## Phase 6 — End-to-end demo

**Deliverables**

- Demo script: detect → inject fault → anomaly → diagnose → recover.
- Screenshots/GIF and a reproducible walkthrough.
- Final documentation pass.

**Exit criteria**

- [ ] One command (or documented sequence) reproduces the demo.
- [ ] Every earlier phase's checks still pass.
- [ ] `pre-commit run --all-files` is clean.
