# Architecture

ChaosPilot is four cooperating subsystems around one SQLite database. All
privileged work (Docker, ML, LLM) happens in the backend; the browser is a
read-mostly dashboard with explicit run and plan actions.

## 1. Components

```mermaid
flowchart TB
    subgraph Browser["Browser"]
        Dashboard["React dashboard<br/>React Flow · Recharts · Zustand"]
    end

    subgraph Backend["ChaosPilot API — FastAPI (:8090)"]
        App["app.py<br/>REST + WebSocket"]
        Runner["experiments.py<br/>ExperimentRunner"]
        Collector["collector.py<br/>1 s probe loop"]
        Runtime["runtime.py<br/>status + score + postmortem"]
        DB[("db.py<br/>SQLite")]
        Hub["ws.py<br/>EventHub"]
        Chaos["chaos/engine.py<br/>HTTP + Docker faults"]
        Detector["ml/detector.py<br/>Isolation Forest"]
        Agent["agent/service.py<br/>planner + postmortem"]
        Topo["topology.py · service_map.py"]
        StackCtl["stack.py<br/>compose restarts"]
    end

    subgraph SampleStack["Sample stack — Docker Compose"]
        Gateway["gateway :8000"]
        Auth["auth :8001"]
        Orders["orders :8002"]
        Cache["cache :8003"]
        Payments["payments :8004"]
        Db["db :8005"]
        Gateway --> Auth
        Gateway --> Orders
        Auth --> Cache
        Orders --> Payments
        Orders --> Db
        Payments --> Db
    end

    subgraph External["External services"]
        LLM["Ollama / OpenAI-compatible"]
        Docker["Docker daemon<br/>compose project chaospilot"]
    end

    Dashboard -->|REST| App
    Hub -->|WebSocket| Dashboard
    App --> Runner
    App --> Agent
    App --> Topo
    Runner --> Collector
    Runner --> Chaos
    Runner --> StackCtl
    Runner --> Runtime
    Runner --> Detector
    Runner --> DB
    Runner --> Hub
    Runner --> Agent
    Collector --> DB
    Collector -->|/health + /checkout| SampleStack
    Agent --> DB
    Agent --> Detector
    Agent --> LLM
    Agent --> Hub
    Chaos -->|HTTP /_chaos| SampleStack
    Chaos -->|SDK| Docker
    StackCtl -->|docker compose up| Docker
    Docker --> Gateway
```

## 2. Data flow

The live experiment path is a single loop: the collector writes samples, the
runner turns them into events, the agent turns the stored evidence into a
report.

```mermaid
flowchart LR
    Request["POST /experiments/run<br/>or POST /agent/plan"] --> Runner
    Runner -->|"fixes=true"| Restart["Recreate stack with<br/>RESILIENT=true"]
    Restart --> Baseline
    Runner --> Baseline["Baseline 10 s"]
    Baseline -->|"median latency per service"| Fault
    Baseline -->|"sampled every 1 s"| Samples[("samples")]
    Fault["Fault 20 s<br/>kill · latency · memory"] -->|"worst status per service"| LiveScore["Live score"]
    Fault -->|"5 s windows"| Windows["Feature windows"]
    Windows --> Detector["Anomaly detector"]
    Detector -->|"anomaly 0-1"| LiveScore
    LiveScore -->|"score event"| Hub["WebSocket hub"]
    Fault --> Recovery["Recovery 10 s"]
    Recovery --> Report["Final score from<br/>fault-window statuses"]
    Report --> Context["Agent context:<br/>topology · timeline · anomalies · phases"]
    Context --> LLM["LLM (optional)"]
    Context --> Template["Deterministic template"]
    LLM --> Postmortem["postmortem event"]
    Template --> Postmortem
    Postmortem --> Hub
    Report --> Store[("experiment_runs")]
    Hub --> Dashboard["Dashboard"]
```

## 3. Experiment sequence

```mermaid
sequenceDiagram
    autonumber
    participant D as Dashboard
    participant A as FastAPI
    participant R as ExperimentRunner
    participant S as StackController
    participant C as Collector
    participant X as Chaos engine
    participant P as Sample stack
    participant DB as SQLite
    participant H as EventHub
    participant G as Agent

    D->>A: POST /experiments/run {fault,target,fixes}
    A->>R: start(...)
    R-->>H: log "experiment started"

    opt fixes = true
        R->>S: restart(resilient=true)
        S->>P: docker compose up -d --force-recreate
        S-->>R: healthy
    end

    R->>C: start(label_resolver, on_samples)
    loop every 1 s for 10 s baseline
        C->>P: GET /health, POST /checkout
        C->>DB: insert samples
        C->>R: on_samples(...)
        R->>H: state, metrics, anomaly, score
    end
    R->>DB: baseline median per service

    R->>X: inject fault
    X->>P: /_chaos/latency, /_chaos/memory or Docker kill
    loop every 1 s for 20 s fault
        C->>P: probes
        C->>DB: insert labelled samples
        C->>R: on_samples(...)
        R->>H: state, metrics, anomaly, score
    end

    R->>X: reset_all / restore
    loop every 1 s for 10 s recovery
        C->>P: probes
        C->>R: on_samples(...)
        R->>H: state, metrics, anomaly, score
    end

    R->>DB: samples_between(fault_started, fault_ended)
    R->>R: worst status per service -> resilience breakdown
    R->>G: finish(run)
    G->>DB: topology + timeline + anomalies + phases
    opt LLM configured and reachable
        G->>G: planner/postmortem prompt -> JSON
    end
    G-->>R: Postmortem (source: llm or template)
    R->>DB: update experiment_runs(score, postmortem)
    R->>H: score + postmortem
    H-->>D: WebSocket frames
```

## 4. Backend modules

| Module | Responsibility |
| --- | --- |
| `backend/app.py` | FastAPI app: `/health`, `/topology`, `/experiments`, `/agent`, `/ws`, CORS, lifespan |
| `backend/api_config.py` | Env-driven settings: DB path, phase lengths, latency, memory, CORS |
| `backend/topology.py` | Static six-service graph and dependency edges |
| `backend/service_map.py` | Canonical service names and host ports 8000-8005 |
| `backend/stack.py` | Compose restarts with `RESILIENT=true|false`, health waits |
| `backend/experiments.py` | Background run lifecycle, live events, final score |
| `backend/collector.py` | 1 s probing of every service plus a gateway checkout |
| `backend/db.py` | SQLite schema and queries for experiments, samples and runs |
| `backend/runtime.py` | Status derivation, resilience formula, phase stats, postmortem text |
| `backend/ws.py` | WebSocket fan-out with stale-client cleanup |
| `backend/chaos/engine.py` | HTTP `/_chaos` faults plus Docker `kill`/`restore` |
| `backend/ml/*` | Feature windows, dataset generation, training, evaluation, detector |
| `backend/agent/*` | Tools, planner, postmortem writer, LLM plumbing, context builder |

The earlier `backend/core/` scaffold is still imported for typed settings
(`core/config.py`) and the shared LLM client (`core/agent/llm.py`). Its API
routers are **not** mounted by `backend/app.py`; the served API is the Phase 7
app.

## 5. Data model

```sql
experiments(id, fault, target, started, ended, fixes_on)

samples(id, experiment_id, ts, service, up, latency_ms, error, label)
-- label = 1 inside the fault window, 0 otherwise

experiment_runs(
    experiment_id, status, resilient,
    baseline_end, fault_started, fault_ended, recovery_end,
    score, postmortem, error
)
```

`samples` is append-only. Timestamps are Unix seconds (UTC). SQLite runs in WAL
mode; one experiment writes at a time, so writes stay small and serialised.

## 6. Event contract

| Event | Payload |
| --- | --- |
| `state` | `service`, `status` (`ok`/`warn`/`bad`), `latency_ms` |
| `log` | `level`, `text` (experiment, agent steps, errors) |
| `metrics` | `gateway_latency`, `error_rate` |
| `anomaly` | `value` (0-1), `services` map |
| `score` | `value`, `failed[]`, `degraded[]`, `contained`, `bonus` |
| `postmortem` | `text`, `source` (`llm`/`template`), `structured` |

A `state` event is sent for each service every tick, followed by one `metrics`,
one `anomaly` and one `score`. The run ends with `score` and `postmortem`.

## 7. Scoring and status rules

| Status | Rule |
| --- | --- |
| `bad` | service is down or the request errored |
| `warn` | latency is more than 3x the baseline median |
| `ok` | everything else |

```text
score = 100 - 15 * failed - 6 * degraded + (10 if fixes and contained else 0)
```

Containment means every service outside `affected_services(target)` — the
target plus its transitive callers — stayed `ok`. The value is clamped to
0-100. The final score uses the worst status each service reached during the
fault window; the live score is frozen the same way so recovery cannot raise it.

## 8. Failure modes and design choices

- **Docker unavailable**: latency and memory faults still work over HTTP; `kill`
  reports a clear engine error.
- **Model artifact missing**: the runner falls back to a baseline-ratio anomaly
  score; the API keeps streaming.
- **LLM unavailable**: the planner falls back to a rule (`latency` on the
  service with the most callers) and the postmortem falls back to a template.
- **Not enough telemetry**: status derivation and the heuristic anomaly score
  handle empty windows without raising.
- **Public repository**: env-only configuration, gitleaks plus a local guard,
  and a backend-only LLM boundary are architectural requirements.
- **Frontend offline**: the dashboard keeps the bundled topology, shows a
  backend-unreachable banner and reconnects with exponential backoff.
