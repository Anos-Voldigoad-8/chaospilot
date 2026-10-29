# Sample stack

A six-container FastAPI lab for ChaosPilot. One gateway sits in front of five
small services with real HTTP dependencies.

```text
                    ┌─────────┐
        port 8000   │ gateway │
                    └──┬───┬──┘
             ┌─────────┘   └─────────┐
       ┌─────▼─────┐           ┌─────▼──────┐
       │   auth    │           │   orders   │
       └─────┬─────┘           └──┬──────┬──┘
       ┌─────▼─────┐        ┌─────▼──┐ ┌─▼─────┐
       │   cache   │        │payments│ │  db   │
       └───────────┘        └────┬───┘ └─▲─────┘
                                 └───────┘
```

| Service | Host port | Dependencies |
| --- | --- | --- |
| gateway | 8000 (public entry point) | auth, orders |
| auth | 8001 | cache |
| orders | 8002 | payments, db |
| cache | 8003 | — (in-memory dict) |
| payments | 8004 | db |
| db | 8005 | — (in-memory tables) |

Only the gateway is meant for users; the other host ports exist so ChaosPilot's
collector and chaos engine can reach each service directly.

## Run

```bash
docker compose config
docker compose up --build
```

Then:

```bash
curl http://localhost:8000/checkout
```

Expected shape (order ids and timings vary):

```json
{
  "status": "ok",
  "degraded": false,
  "auth": {"verified": true, "user": "user-42", "cached": true, "degraded": false},
  "order": {
    "order_id": "ord_…",
    "status": "created",
    "degraded": false,
    "stored": true,
    "payment": {"charge_id": "ch_…", "status": "captured", "stored": true}
  }
}
```

Everything uses `httpx` over the Compose network. Cache and database state is
in-memory and disappears when their containers restart.

## Endpoints on every service

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Status, p50 latency of the last 20 requests, resilience mode, held memory |
| GET | `/metrics` | Collector-friendly sample (p50, error rate, CPU, RSS) |
| POST | `/_chaos/latency` | Body `{"ms": 1500}` — delay every request by that amount |
| POST | `/_chaos/memory` | Body `{"mb": 256}` — allocate and hold memory |
| POST | `/_chaos/reset` | Clear latency and release all held memory |

Service-specific routes:

| Service | Routes |
| --- | --- |
| gateway | `GET /checkout` |
| auth | `GET /verify` |
| orders | `POST /create` |
| cache | `GET/POST /cache/{key}` |
| payments | `POST /charge` |
| db | `GET/POST /records/{table}/{key}`, `GET /tables/{table}` |

## Default vs resilient mode

The default profile is intentionally fragile: **one attempt, a 5 second
timeout and no circuit breaker**. A single failed dependency propagates as a
`502` with the dependency URL, which is exactly what ChaosPilot should expose.

Set `RESILIENT=true` to enable, per service:

- **one retry** (two attempts total, 50 ms apart),
- a **1 second** timeout,
- a **circuit breaker** (3 consecutive failures → open for 10 seconds),
- a **fallback response** while the breaker is open or the call still fails.

```bash
# Linux/macOS
RESILIENT=true docker compose up --build
```

```powershell
# Windows PowerShell
$env:RESILIENT="true"; docker compose up --build
```

`GET /health` reports `resilient`, `http_timeout_seconds`, `retries` and
`circuit_breaker`, so the before/after is visible without reading code.

Try it:

```bash
# Stop a dependency, then compare the gateway response
docker compose stop cache
curl -i http://localhost:8000/checkout   # default: 502
```

With `RESILIENT=true`, auth returns a fallback (`user: anonymous`,
`degraded: true`) and the checkout call keeps working in degraded mode.

## Chaos examples

```bash
# Add 1s to every gateway request, then inspect /health p50
curl -X POST http://localhost:8000/_chaos/latency \
  -H "Content-Type: application/json" -d '{"ms":1000}'
time curl http://localhost:8000/checkout
curl http://localhost:8000/health

# Hold 256 MB in the db process
curl -X POST http://localhost:8005/_chaos/memory \
  -H "Content-Type: application/json" -d '{"mb":256}'
curl http://localhost:8005/health

# Clear everything
curl -X POST http://localhost:8000/_chaos/reset
curl -X POST http://localhost:8005/_chaos/reset
```

## Notes

- No secrets are defined here. The optional `env_file` points at the
  repository-root `.env`; missing files are allowed.
- There are no retries or timeouts above 5 seconds in the default path.
- Every service is built from the same `Dockerfile`; `SERVICE_NAME` selects the
  code copied into the image.
