# API reference

Base URL: `http://127.0.0.1:8090`. All REST responses are JSON. No
authentication (local-only tool). Interactive docs: `/docs`.

The API runs separately from the sample-stack gateway on port 8000.

## System

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | API liveness, active experiment, WebSocket client count |
| `GET` | `/topology` | Sample-stack nodes (with host ports) and directed edges |

### `GET /topology`

```json
{
  "nodes": [
    {"id": "gateway", "label": "gateway", "port": 8000, "role": "entry point", "entry": true},
    {"id": "auth", "label": "auth", "port": 8001, "role": "session verification", "entry": false}
  ],
  "edges": [
    {"id": "gateway->auth", "source": "gateway", "target": "auth"}
  ]
}
```

## Experiments

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/experiments/run` | Start an experiment in the background (`202`) |
| `GET` | `/experiments?limit=50` | Experiment history, newest first |
| `GET` | `/experiments/{id}` | One experiment with samples, phases and labels |

### `POST /experiments/run`

```json
{
  "fault": "latency",
  "target": "payments",
  "fixes": false
}
```

- `fault`: `kill`, `latency` or `memory`.
- `target`: `gateway`, `auth`, `orders`, `cache`, `payments` or `db`.
- `fixes`: when `true`, the stack is restarted through Docker Compose with
  `RESILIENT=true` before the baseline (1 retry, 1 s timeout, circuit breaker,
  fallback responses). Defaults to `false`.

One run is **10 s baseline → 20 s fault → 10 s recovery**. Only one run can be
active at a time. Timings and fault parameters can be overridden through
`CHAOSPILOT_BASELINE_SECONDS`, `CHAOSPILOT_FAULT_SECONDS`,
`CHAOSPILOT_RECOVERY_SECONDS`, `CHAOSPILOT_LATENCY_MS` and
`CHAOSPILOT_MEMORY_MB`.

`202` response:

```json
{
  "id": 1,
  "status": "pending",
  "fault": "latency",
  "target": "payments",
  "fixes": false
}
```

### `GET /experiments/{id}`

```json
{
  "id": 1,
  "fault": "latency",
  "target": "payments",
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
  "postmortem": "Experiment #1: injected latency on payments ...",
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
    {"id": 1, "experiment_id": 1, "ts": 1790000001.0, "service": "gateway", "up": 1, "latency_ms": 70.2, "error": 0, "label": 0}
  ]
}
```

`phases` contains gateway `/checkout` statistics. `samples` contains every
service probe, labelled `1` only inside the fault window.

Status derivation per service:

| Status | Rule |
| --- | --- |
| `bad` | service is down or the request errored |
| `warn` | latency is more than 3x the baseline median |
| `ok` | everything else |

## WebSocket

`ws://127.0.0.1:8090/ws` accepts multiple dashboard clients and broadcasts
JSON frames:

```json
{"type": "state", "service": "payments", "status": "warn", "latency_ms": 2013.0}
{"type": "log", "level": "warn", "text": "Fault active: latency on payments"}
{"type": "metrics", "gateway_latency": 2073.3, "error_rate": 0.0}
{"type": "score", "value": 40.0}
{"type": "postmortem", "text": "Experiment #1: injected latency ..."}
```

A `state` event is sent for every service on every collector tick (1 s), then
one `metrics` and one `score` event. The stream ends each run with `score` and
`postmortem`. A small client is included:

```bash
cd backend
python scripts/ws_client.py --fault latency --target payments
```

## CORS

The API allows `http://localhost:5173` and `http://127.0.0.1:5173`
(override with `CHAOSPILOT_CORS_ORIGINS`).

## Errors

| Status | Meaning |
| --- | --- |
| `400` | Unknown target service |
| `404` | Unknown experiment id |
| `409` | An experiment is already running |
| `422` | Schema validation error (FastAPI) |

Error body: `{"detail": "human readable message"}`.
