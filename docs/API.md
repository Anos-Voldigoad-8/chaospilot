# API reference

Base URL: `http://127.0.0.1:8090`. All REST responses are JSON. No
authentication (local-only tool). Interactive docs: `/docs`.

## System

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | API liveness, active experiment, WebSocket client count |
| `GET` | `/topology` | Simulated service nodes and directed dependency edges |

### `GET /topology`

```json
{
  "nodes": [
    {"id": "gateway", "label": "gateway", "role": "public entry point",
     "baseline_latency_ms": 60.0, "baseline_error_rate": 0.005,
     "load_capacity_rps": 1000.0, "entry": true},
    {"id": "auth", "label": "auth", "role": "session verification", ...}
  ],
  "edges": [
    {"id": "gateway->auth", "source": "gateway", "target": "auth"},
    {"id": "gateway->orders", "source": "gateway", "target": "orders"},
    {"id": "auth->cache", "source": "auth", "target": "cache"},
    {"id": "orders->payments", "source": "orders", "target": "payments"},
    {"id": "orders->db", "source": "orders", "target": "db"},
    {"id": "payments->db", "source": "payments", "target": "db"}
  ]
}
```

## Data collection (agent)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/agent/status` | Provider mode and model, never a key |
| `POST` | `/agent/collect` | Run the data agent: public data → scenarios |
| `GET` | `/scenarios?limit=50` | Agent-stored scenarios, newest first |

### `POST /agent/collect`

Runs the data agent, which fetches real outage and traffic from keyless public
APIs (Statuspage incident feeds, GitHub public events, Open-Meteo weather),
converts them into scenarios, and persists them to SQLite. Progress streams over
WebSocket. Falls back to cache, then to the committed seed dataset when the
network is down; never crashes.

Response:

```json
{
  "scenarios": [
    {
      "id": 1,
      "fault_type": "latency",
      "target_service": "gateway",
      "duration_minutes": 15,
      "severity": "medium",
      "load_curve": [{"t": "2026-11-01T00:00", "v": 0.72}, ...],
      "source": "github",
      "source_url": "https://api.github.com/events",
      "data_source": "live",
      "title": "github activity: PushEvent",
      "created_at": 1790000000.0
    }
  ],
  "count": 4
}
```

`data_source` is `live`, `cached` or `seed` and drives the dashboard's "Data
source" badge (LIVE / CACHED / SEED). The `source_url` is the real public API
URL used.

## Scenarios

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/scenarios` | List scenarios (title, source, target, severity, data source) |

### `GET /scenarios`

Each scenario carries `fault_type` (`kill`, `latency` or `memory`),
`target_service`, `duration_minutes`, `severity`, `load_curve`, `source`,
`source_url`, `data_source`, `title` and `created_at`.

## Experiments

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/experiments/run` | Start a scenario experiment in the background (`202`) |
| `GET` | `/experiments?limit=50` | Experiment history, newest first |
| `GET` | `/experiments/{id}` | One experiment with samples, phases and labels |

### `POST /experiments/run`

An experiment can **only** run a scenario stored by the data agent. There is no
hardcoded or manual fault selection.

```json
{
  "scenario_id": 1,
  "fixes": false
}
```

- `scenario_id`: id of a scenario returned by `GET /scenarios`.
- `fixes`: when `true`, the simulator applies retry, timeout and circuit
  breaker, containing the blast radius to one hop. Defaults to `false`.

One run is **baseline → fault → recovery** (timings from
`SIM_BASELINE_SECONDS`, `SIM_FAULT_SECONDS`, `SIM_RECOVERY_SECONDS`, default
10/20/10 s). Only one run can be active at a time.

`202` response:

```json
{
  "id": 1,
  "status": "pending",
  "scenario_id": 1,
  "fault_type": "latency",
  "target_service": "gateway",
  "fixes": false
}
```

### `GET /experiments/{id}`

```json
{
  "id": 1,
  "fault_type": "latency",
  "target_service": "gateway",
  "fixes": false,
  "resilient": false,
  "status": "completed",
  "started": 1790000000.0,
  "baseline_end": 1790000010.0,
  "fault_started": 1790000010.1,
  "fault_ended": 1790000030.2,
  "recovery_end": 1790000040.3,
  "ended": 1790000040.3,
  "score": 40.0,
  "postmortem": "Experiment #1: latency on gateway from scenario #1 ...",
  "error": null,
  "sample_count": 240,
  "error_count": 0,
  "labels": {"normal": 180, "fault": 60},
  "phases": {
    "baseline": {"samples": 10, "errors": 0, "fault_labels": 0, "p50_ms": 68.5, "max_ms": 193.8},
    "fault": {"samples": 20, "errors": 0, "fault_labels": 20, "p50_ms": 2081.8, "max_ms": 2087.2},
    "recovery": {"samples": 10, "errors": 0, "fault_labels": 0, "p50_ms": 69.1, "max_ms": 2085.6}
  },
  "samples": [
    {"id": 1, "experiment_id": 1, "ts": 1790000001.0, "service": "gateway",
     "up": 1, "latency_ms": 70.2, "error": 0, "label": 0}
  ]
}
```

`phases` contains gateway statistics. `samples` contains every service probe,
labelled `1` only inside the fault window. The postmortem text references the
scenario's real title and source.

Status derivation per service:

| Status | Rule |
| --- | --- |
| `bad` | service is down or the request errored (failed) |
| `warn` | latency is more than 3x the baseline median (degraded) |
| `ok` | everything else |

### Resilience score

The score uses the worst status each service reached during the fault window:

```text
score = 100
      - 15 * failed services
      -  6 * degraded services
      + 10 if fixes were enabled and the blast radius stayed contained
```

Containment means no service outside the target's one-hop blast radius (the
target plus its direct callers) failed or degraded. The result is clamped to
`0..100`. `Compare` keeps the last run with fixes off next to the last run with
fixes on.

## WebSocket

`ws://127.0.0.1:8090/ws` accepts multiple dashboard clients and broadcasts
JSON frames:

```json
{"type": "state", "service": "payments", "status": "warn", "latency_ms": 2013.0}
{"type": "log", "level": "warn", "text": "collect data // github live"}
{"type": "log", "level": "info", "text": "Fault active: latency on payments"}
{"type": "metrics", "gateway_latency": 2073.3, "error_rate": 0.0}
{"type": "anomaly", "value": 0.93,
 "services": {"payments": 0.93, "gateway": 0.71, "db": 0.08}}
{
  "type": "score",
  "value": 64.0,
  "failed": ["payments"],
  "degraded": ["gateway", "orders", "db"],
  "contained": false,
  "bonus": 0.0
}
{
  "type": "postmortem",
  "text": "...",
  "source": "template",
  "structured": null
}
```

A `state` event is sent for every service on every tick, then one `metrics`,
one `anomaly` and one `score` event. The anomaly score comes from the Isolation
Forest when a model is available, with a heuristic fallback otherwise. The
stream ends each run with `score` and `postmortem`; `source` is `llm` or
`template`. A small client is included:

```bash
cd backend
python scripts/ws_client.py
```

## CORS

The API allows `http://localhost:5173` and `http://127.0.0.1:5173`
(override with `CHAOSPILOT_CORS_ORIGINS`).

## Errors

| Status | Meaning |
| --- | --- |
| `400` | Unknown scenario id or unsupported fault type |
| `404` | Unknown experiment id |
| `409` | An experiment is already running |
| `422` | Schema validation error (FastAPI) |

Error body: `{"detail": "human readable message"}`.
