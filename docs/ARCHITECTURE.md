# Architecture

ChaosPilot is organised as four cooperating subsystems around a shared SQLite
database. The backend owns all privileged work (Docker, ML, LLM); the frontend
is a read-mostly dashboard with explicit control actions.

## 1. Component overview

```text
┌──────────────────────────── frontend (React/Vite) ───────────────────────────┐
│  Topology (React Flow)   Metrics (Recharts)   Incidents + Agent report        │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                    │ REST (JSON) + polling
┌───────────────────────────────────▼───────────────────────────────────────────┐
│                              backend (FastAPI)                                │
│                                                                               │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │  Collector   │──▶│   SQLite     │◀──│  Chaos       │   │  Incident      │  │
│  │  (async loop)│   │  metrics     │   │  manager     │   │  agent (LLM)   │  │
│  └──────┬───────┘   │  anomalies   │   └──────┬───────┘   └───────┬────────┘  │
│         │           │  faults      │          │                   │           │
│         │           │  incidents   │          │                   │           │
│         │           └──────┬───────┘          │                   │           │
│         │                  │                  │                   │           │
│  ┌──────▼───────┐   ┌──────▼───────┐   ┌──────▼───────┐   ┌───────▼────────┐  │
│  │  Telemetry   │   │  Anomaly     │   │ Docker SDK   │   │ Ollama /       │  │
│  │  sources     │   │  detector    │   │ (faults)     │   │ OpenAI API     │  │
│  └──────┬───────┘   └──────────────┘   └──────┬───────┘   └───────┬────────┘  │
└─────────┼──────────────────────────────────────┼───────────────────┼──────────┘
          │ /metrics, /health                    │ stop/exec/network │ HTTP
┌─────────▼──────────────────┐          ┌────────▼───────────────────▼──────────┐
│ sample-stack (6 services)  │          │ Docker daemon                         │
│ gateway auth orders        │◀─────────│ compose project "chaospilot"          │
│ cache payments db          │  faults  └───────────────────────────────────────┘
└────────────────────────────┘
```

## 2. Backend modules

The served API is the Phase 3 app at `backend/app.py`:

| Module | Responsibility |
| --- | --- |
| `app.py` | FastAPI app: topology, experiments, WebSocket, CORS |
| `api_config.py` | Env-driven Phase 3 settings |
| `topology.py` | Static sample-stack nodes and edges |
| `stack.py` | Docker Compose restarts with `RESILIENT=true|false` |
| `experiments.py` | Background run lifecycle and event broadcasting |
| `collector.py` | 1 s probing of `/health` plus gateway `/checkout` |
| `db.py` | SQLite experiments, samples and run metadata |
| `runtime.py` | Status derivation, resilience score, postmortem text |
| `ws.py` | WebSocket fan-out to dashboard clients |
| `chaos/engine.py` | Docker `kill`/`restore` and HTTP `/_chaos/*` faults |

### Legacy core scaffold

The earlier scaffold remains under `backend/core/` and is not the served
entrypoint. It contains the IsolationForest detector and LLM agent work:

| Module | Responsibility |
| --- | --- |
| `core/config.py` | Typed environment settings; only place that reads `.env` |
| `core/database.py` | SQLite connection factory, schema, WAL mode |
| `core/services/registry.py` | Canonical service catalogue and dependencies |
| `core/services/store.py` | Queries for services, metrics, faults, incidents |
| `core/collector/simulator.py` | Synthetic telemetry when Docker is absent |
| `core/collector/collector.py` | Async polling loop; persists samples; triggers detection |
| `core/ml/features.py` | Feature extraction from metric rows |
| `core/ml/detector.py` | StandardScaler + IsolationForest, persisted with pickle |
| `core/ml/service.py` | Train, score, de-duplicate and persist anomalies |
| `core/chaos/models.py` | Fault types, parameters, validation |
| `core/chaos/engine.py` | Docker SDK fault application/recovery |
| `core/chaos/manager.py` | Fault lifecycle: inject → active → recover/expire |
| `core/agent/llm.py` | Ollama and OpenAI-compatible clients (backend only) |
| `core/agent/prompts.py` | Grounded prompt templates |
| `core/agent/agent.py` | Context assembly, LLM call, fallback analysis, incidents |
| `core/api/*` | Versionless JSON API routers + Pydantic schemas |

### Data flow (legacy core pipeline)

1. Collector asks each service for `/metrics` (or the simulator invents a
   sample, including any active fault effect).
2. Sample is written to `metrics`.
3. Detector scores the newest sample per service. Anomalies above the
   severity floor are stored in `anomalies` with a per-service cooldown.
4. Frontend polls `/api/overview` and renders topology + charts.
5. Operator (or the demo script) injects a fault via `/api/faults`.
6. Operator asks `/api/agent/diagnose`; the agent reads metrics, anomalies and
   fault history from SQLite, calls the LLM, and stores an `incident`.

## 3. Data model

```sql
services(id, name, port, url, dependencies, created_at)
metrics(id, service_id, ts, latency_ms, error_rate, cpu_percent,
        memory_mb, request_rate)
anomalies(id, service_id, metric, value, score, severity, detected_at,
          details)
faults(id, service_id, fault_type, parameters, status, started_at,
       ends_at, recovered_at)
incidents(id, service_id, anomaly_id, summary, root_cause, evidence,
          recommendations, confidence, provider, created_at)
```

`metrics` is append-only. Collector retention deletes rows older than
`CHAOSPILOT_HISTORY_MINUTES`. All timestamps are Unix seconds (UTC).

## 4. Chaos model

Supported faults:

| Fault | Docker action | Simulation effect |
| --- | --- | --- |
| `latency` | `POST /admin/fault` on the target | latency += parameter |
| `error` | same, raises error rate | error_rate ↑, requests ↓ |
| `crash` | `container.stop()` | 100% errors, zero traffic |
| `cpu` | detached busy-loop `exec` | cpu_percent ↑, latency ↑ |
| `memory` | `container.update(mem_limit=...)` | memory ↑, latency ↑ |
| `network` | disconnect/reconnect container | error_rate ↑, latency ↑ |

Recovery is explicit (`POST /api/faults/{id}/recover`) or automatic when
`ends_at` passes. The manager restores the previous container state.

## 5. Anomaly detection

Features: `latency_ms`, `error_rate`, `cpu_percent`, `memory_mb`,
`request_rate`.

- **Training**: last 500 samples per service, standardised, IsolationForest
  with `contamination=0.04`, `n_estimators=150`, random seed 42.
- **Scoring**: `-decision_function` (higher = more anomalous). Severity bands
  come from score quantiles (`low` / `medium` / `high` / `critical`).
- **Cold start / fallback**: fewer than 30 samples or scikit-learn missing →
  robust z-score against the rolling median/MAD.
- **Persistence**: `backend/models/anomaly_detector.pkl` (git-ignored).
  Retraining is available via `POST /api/anomalies/train`.

The model is intentionally simple: the project's value is the closed loop, not
a state-of-the-art detector.

## 6. LLM agent

- Default provider is **Ollama** (`http://localhost:11434`), so no key is
  required. Hosted OpenAI-compatible APIs are supported by setting
  `LLM_PROVIDER=openai` and `OPENAI_API_KEY` in `.env`.
- The key is read only in `core/config.py` and used only in
  `core/agent/llm.py`. It is never returned by an endpoint, logged, or sent to
  the frontend.
- The prompt contains: service metadata, dependency edges, the anomaly, the
  last N metric samples, recent faults, and recent incidents. The model must
  answer as strict JSON: `summary`, `root_cause`, `evidence[]`,
  `recommendations[]`, `confidence`.
- If the LLM is unreachable or returns invalid JSON, a deterministic
  rule-based analyser produces a diagnosis so the demo always works. The
  response's `provider` field says which path was used (`ollama`, `openai`,
  or `fallback`).

## 7. Frontend

- Single-page dashboard with a service topology (React Flow), a time-series
  chart (Recharts), an anomaly feed, a fault injection panel and an incident
  report drawer.
- Polls `/api/overview` every 5 seconds; mutations invalidate immediately.
- `src/lib/api.ts` is the only file that knows URLs. It reads
  `VITE_API_BASE_URL` (public, non-secret).
- No key, token or password ever reaches the bundle. Anything secret is
  requested from the backend.

## 8. Failure modes and design choices

- **Docker unavailable** → simulation mode keeps the whole product usable.
- **LLM unavailable** → deterministic fallback keeps diagnoses available.
- **Not enough telemetry** → statistical detector instead of a broken model.
- **SQLite concurrency** → WAL plus per-request connections; writes are tiny
  and serialised by the single collector loop.
- **Public repository** → secret scanning, env-only configuration and a
  backend-only LLM boundary are architectural requirements, not extras.
