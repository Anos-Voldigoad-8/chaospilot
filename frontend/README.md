# ChaosPilot frontend

Cyberpunk HUD dashboard for the Phase 3 backend: a live service map, a
resilience gauge, streaming p95/error charts, the agent console and a typed
postmortem report.

React 18 + Vite + TypeScript + Tailwind. React Flow renders the service graph,
Recharts renders telemetry, Zustand holds dashboard state.

## Run

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production bundle
```

The backend must listen on `http://127.0.0.1:8090`:

```bash
cd backend
uvicorn app:app --reload --port 8090
```

Vite proxies `/topology`, `/experiments`, `/agent`, `/health` and `/ws` to that
port, so the browser only ever talks to one origin and no port is hardcoded in
the app.

### Demo without the backend

Append `?mock=1` to the URL:

<http://localhost:5173/?mock=1>

Mock mode replays a compressed scripted experiment (roughly 15 seconds) and
emits the exact WebSocket event shapes the backend sends: service states,
metrics, anomaly scores, resilience breakdown, logs and the final postmortem.
The RUN button replays it again; AGENT MODE picks the plan locally.

## Controls

- **RUN** posts the selected fault/target to `/experiments/run`.
- **AGENT MODE** calls `/agent/plan`, shows the hypothesis, then runs it.
- **Apply fixes** restarts the stack with `RESILIENT=true` before the baseline.
- **Compare** keeps the last score with fixes off next to the last with fixes on.
- The status bar shows a clear banner when the backend cannot be reached; the
  dashboard keeps retrying in the background.

## Configuration

Only public, non-secret values are read:

```dotenv
# Blank = same-origin through the Vite proxy (recommended).
VITE_API_BASE_URL=
VITE_WS_URL=

# 1 = always use the scripted feed; same as ?mock=1.
VITE_MOCK=0
```

Per-URL overrides:

- `?mock=1` — scripted experiment, no backend needed.
- `?ws=ws://host:port/ws` — one-off WebSocket endpoint.

`VITE_*` variables are embedded in the browser bundle. **Never put API keys,
tokens or passwords in this app or in any `VITE_*` variable.** Every LLM call
is made by the backend.

## Layout

| Area | Contents |
| --- | --- |
| Top bar | Logo, connection status, Apply fixes toggle, clock, offline banner |
| Left | Fault type, target service, RUN, AGENT MODE, agent plan, past experiments |
| Center | React Flow service map with status colours, latency and red propagation |
| Right | Animated SVG resilience gauge, p95 latency, error rate, anomaly score, live chart |
| Bottom | Auto-scrolling agent console, typewriter postmortem and fixes-off/on compare |

Down to tablet widths the map spans the full width first, then control and
telemetry sit side by side, with console and postmortem below.

## Structure

| Path | Purpose |
| --- | --- |
| `src/store/useChaosStore.ts` | All dashboard state, run logic, event ingestion |
| `src/hooks/useWebSocket.ts` | WebSocket link with reconnect/backoff, bootstrap |
| `src/hooks/useAnimation.ts` | Gauge count-up and postmortem typewriter |
| `src/mock/script.ts` | Scripted experiment for `?mock=1` |
| `src/lib/api.ts` | Typed REST client and WebSocket URL resolution |
| `src/lib/topology.ts` | Fallback topology and fixed graph layout |
| `src/components/ServiceMap.tsx` | React Flow map, custom nodes, edge colouring |
| `src/components/ControlPanel.tsx` | Fault/target selectors, RUN, AGENT MODE, run history |
| `src/components/LiveMetrics.tsx` | Gauge, p95, error, anomaly, Recharts stream |
| `src/components/ComparePanel.tsx` | Last fixes-off vs fixes-on resilience score |
| `src/components/AgentConsole.tsx` | Colour-coded, auto-scrolling log |
| `src/components/PostmortemPanel.tsx` | Typed agent report |
| `src/types/chaos.ts` | Backend event and API types |

No local state is persisted; SQLite in the backend is the source of truth.
