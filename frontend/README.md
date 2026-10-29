# ChaosPilot frontend

React 18 + Vite + TypeScript + Tailwind dashboard. React Flow renders the
service topology; Recharts renders telemetry.

## Run

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production bundle
```

The Vite dev server proxies `/api` and `/health` to `http://127.0.0.1:8000`,
so the backend must be running.

## Configuration

Only public, non-secret values may be exposed:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

`VITE_*` variables are embedded in the browser bundle. **Never put API keys,
tokens or passwords in this app or in any `VITE_*` variable.** Every LLM call
is made by the backend; the browser only calls `POST /api/agent/diagnose`.

## Structure

| Path | Purpose |
| --- | --- |
| `src/lib/api.ts` | Typed API client, the only place that knows URLs |
| `src/hooks/` | Polling hooks for overview and metrics |
| `src/components/Topology.tsx` | React Flow service graph |
| `src/components/MetricsChart.tsx` | Recharts time series |
| `src/components/FaultPanel.tsx` | Fault injection / recovery |
| `src/components/AgentPanel.tsx` | Incident report + diagnosis trigger |
| `src/types/api.ts` | API types |

No local state is persisted; the backend (SQLite) is the source of truth.
