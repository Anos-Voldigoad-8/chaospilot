# Sample stack

Five deliberately small FastAPI services that ChaosPilot can observe and
break. Each service exposes the same operational surface:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Liveness and current fault state |
| `GET /metrics` | Latency, error rate, CPU, memory, request count |
| `GET /work` | Cheap workload endpoint |
| `POST /admin/fault` | Apply latency/error/CPU/memory fault knobs |
| `POST /admin/reset` | Clear fault knobs |

## Topology

```text
catalog        cart
      \        /
       checkout ──▶ payments
            \
             └──▶ notifications
```

`checkout` calls `cart`, `payments` and `notifications`, so a fault on a leaf
service propagates into checkout telemetry — exactly what the diagnosis agent
is meant to untangle.

## Run

```bash
# optional: configure ports/log level from the repo-root .env
docker compose config
docker compose up --build
```

| Service | Host port |
| --- | --- |
| catalog | 8001 |
| cart | 8002 |
| checkout | 8003 |
| payments | 8004 |
| notifications | 8005 |

Verify:

```bash
curl http://localhost:8003/checkout -X POST -H "Content-Type: application/json" \
  -d '{"cart_id":"cart_demo","amount":42.5}'
```

## Inject a fault manually

```bash
# 1.5s of latency on payments
curl -X POST http://localhost:8004/admin/fault \
  -H "Content-Type: application/json" \
  -d '{"latency_ms":1500}'

# recover
curl -X POST http://localhost:8004/admin/reset
```

Normally ChaosPilot does this through the Docker SDK; the admin endpoints are
only the in-container control surface.

## Notes

- State is in-memory. Restarting a container clears carts, charges and
  notifications.
- The stack has no secrets and no persistence. The optional `env_file` points
  at the repository-root `.env`; missing files are allowed.
- Never add credentials to this compose file. Use `${VAR}` references.
