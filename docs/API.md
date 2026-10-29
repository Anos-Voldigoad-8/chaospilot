# API reference

Base URL: `http://127.0.0.1:8000`. All responses are JSON. No authentication
(local-only tool). Interactive docs: `/docs`.

## System

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness, version, mode, LLM provider |
| `GET` | `/api/overview` | Dashboard snapshot (services, latest metrics, anomalies, faults, incidents) |
| `GET` | `/api/config` | Non-secret runtime capabilities |

### `GET /health`

```json
{
  "status": "ok",
  "version": "0.1.0",
  "simulation_mode": true,
  "docker_enabled": false,
  "llm_provider": "ollama"
}
```

## Services

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/services` | List services with health and latest sample |
| `GET` | `/api/services/{service_id}` | One service |
| `GET` | `/api/metrics?service_id=&minutes=` | Time series |
| `GET` | `/api/metrics/summary?minutes=` | Aggregated per-service summary |

### `GET /api/metrics` response

```json
{
  "service_id": "checkout",
  "minutes": 30,
  "points": [
    {
      "timestamp": 1790000000.0,
      "service_id": "checkout",
      "latency_ms": 48.2,
      "error_rate": 0.01,
      "cpu_percent": 22.4,
      "memory_mb": 180.1,
      "request_rate": 42.0
    }
  ]
}
```

## Anomalies

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/anomalies?limit=&service_id=` | Recent anomalies |
| `POST` | `/api/anomalies/train` | Train/retrain the detector |
| `POST` | `/api/anomalies/detect` | Score latest samples now |

### `POST /api/anomalies/train`

```json
{
  "trained": true,
  "samples": 1500,
  "services": 5,
  "model_path": "models/anomaly_detector.pkl"
}
```

## Faults

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/faults?status=` | List faults (active by default) |
| `POST` | `/api/faults` | Inject a fault |
| `POST` | `/api/faults/{fault_id}/recover` | Recover a fault |

### `POST /api/faults`

```json
{
  "service_id": "checkout",
  "fault_type": "latency",
  "duration_seconds": 120,
  "parameters": { "latency_ms": 1500 }
}
```

Allowed `fault_type`: `latency`, `error`, `crash`, `cpu`, `memory`,
`network`. `duration_seconds` is 10–3600. Parameters are type-specific:

| Type | Parameter | Default |
| --- | --- | --- |
| `latency` | `latency_ms` | 800 |
| `error` | `error_rate` | 0.5 |
| `cpu` | `cpu_percent` | 90 |
| `memory` | `memory_mb` | 512 |
| `network` | `packet_loss` | 1.0 |
| `crash` | — | — |

## Agent and incidents

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/agent/status` | Provider, availability, mode |
| `POST` | `/api/agent/diagnose` | Analyse a service/incident |
| `GET` | `/api/incidents?limit=` | Stored incident reports |
| `GET` | `/api/incidents/{incident_id}` | One incident |

### `POST /api/agent/diagnose`

```json
{
  "service_id": "checkout",
  "anomaly_id": 42
}
```

Response:

```json
{
  "id": "inc_...",
  "service_id": "checkout",
  "anomaly_id": 42,
  "summary": "Checkout latency is elevated by 30x...",
  "root_cause": "An injected latency fault on payments propagates...",
  "evidence": ["latency_ms 1480 > baseline 52", "active latency fault on payments"],
  "recommendations": ["Recover the fault", "Add timeout + circuit breaker"],
  "confidence": 0.82,
  "provider": "fallback",
  "created_at": 1790000000.0
}
```

If the LLM is unavailable the endpoint still responds `200` with
`provider: "fallback"`; the diagnosis is rule-based and clearly labelled.

## Errors

| Status | Meaning |
| --- | --- |
| `400` | Invalid fault parameters / target |
| `404` | Unknown service, fault or incident |
| `422` | Schema validation error (FastAPI) |
| `503` | Docker/LLM requested but unavailable in a strict mode |

Error body: `{"detail": "human readable message"}`.
