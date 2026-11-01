# Report notes

Module-by-module summaries for the write-up. Each section is 5-8 lines and
names the file it describes. Numbers come from the code and from
[`docs/model_metrics.json`](model_metrics.json), not from estimates.

## Backend API and runtime

### `backend/app.py`

- Builds the FastAPI app through `create_app()`, with an injectable engine,
  stack controller, collector factory and agent for tests.
- The lifespan opens `ChaosDatabase`, builds the `AgentService`, the
  `EventHub` and the `ExperimentRunner`, and shuts the runner down on exit.
- Serves `/health`, `/topology`, `POST /experiments/run`, `GET /experiments`,
  `GET /experiments/{id}`, `GET /agent/status` and `POST /agent/plan`.
- `POST /experiments/run` returns `202`; unknown targets map to `400`, a busy
  runner to `409` and an invalid fault to `422`.
- `/ws` accepts a client, sends an initial log frame and keeps the socket open
  until the client disconnects.
- CORS origins come from `ApiSettings`; no credentials or provider keys are
  read here.

### `backend/api_config.py`

- Defines the frozen `ApiSettings` dataclass used by the runner and app.
- Default phase lengths are 10 s baseline, 20 s fault and 10 s recovery.
- The collector interval is 1 s; latency defaults to 2,000 ms and memory to
  256 MB.
- Reads env overrides such as `CHAOSPILOT_BASELINE_SECONDS` and
  `CHAOSPILOT_MEMORY_MB` through small `_env_*` helpers.
- `stack_directory` points at the repository's `sample-stack/`; the default DB
  is `backend/data/chaos.db`.
- Contains no secrets: the LLM provider is configured separately in
  `backend/core/config.py`.

### `backend/topology.py`

- Declares the six sample-stack nodes and their human-readable roles.
- Declares six directed dependency edges from gateway down to `db`.
- `topology()` returns nodes with `id`, `label`, `port`, `role` and `entry`,
  plus edges with `id`, `source` and `target`.
- Node ids and ports are imported from `service_map.py` so the collector,
  chaos engine and dashboard cannot drift.
- The same graph is mirrored in `frontend/src/lib/topology.ts` for first paint
  and offline use.

### `backend/service_map.py`

- Single source of truth for service names and host ports.
- `SERVICE_PORTS` maps gateway to 8000 and auth/orders/cache/payments/db to
  8001-8005.
- `COLLECTOR_SERVICES` excludes the gateway because `/checkout` is probed
  separately.
- `service_url()` validates the service name and returns
  `http://<host>:<port>`.
- Imported by the collector, chaos engine, stack controller and agent tools.

### `backend/stack.py`

- `StackController` owns Compose restarts and health waits for the sample
  stack.
- `restart(resilient=...)` sets `RESILIENT=true|false` in the environment and
  runs `docker compose up -d --force-recreate`.
- A missing `docker` binary, timeout or non-zero exit returns an `ok: false`
  result instead of raising.
- The restart timeout is 180 s and captured output is truncated before it is
  returned.
- `wait_healthy()` polls `/health` on all six services until they answer or the
  90 s health timeout expires.
- The runner calls it before the baseline and after a fixes-on restart.

### `backend/experiments.py`

- `ExperimentRunner` owns one background `asyncio` task per experiment and
  rejects concurrent runs with `ExperimentBusyError`.
- The run is baseline -> fault -> recovery; each phase updates
  `experiment_runs` and broadcasts log frames.
- The collector callback turns each tick into `state`, `metrics`, `anomaly` and
  `score` events.
- Live anomaly scores use `ml.detector.AnomalyDetector` when loadable and a
  baseline-ratio heuristic otherwise.
- The fault window keeps the worst status per service, so the live score cannot
  improve during recovery.
- The final score is computed from the stored fault-window samples and sent
  with `failed`, `degraded`, `contained` and `bonus`.
- Agent hooks (`on_start`, `on_baseline`, `on_fault`, `on_recovery`, `finish`)
  run inside try/except so a broken LLM never stops telemetry.
- Every run ends with a stored postmortem and a `postmortem` WebSocket frame.

### `backend/collector.py`

- The `Collector` is an async loop that probes once per second.
- It probes `/health` on auth, orders, cache, payments and db, and calls the
  gateway `/checkout` as a synthetic user request.
- One timestamp and one label decision are taken per tick so all samples align
  with the experiment window.
- Probe failures are recorded as `up=False`, `error=True` instead of aborting
  the tick.
- Samples are inserted through `ChaosDatabase.insert_samples()` and then passed
  to an optional async `on_samples` callback.
- The loop survives transient database and network errors and stops cleanly via
  an `asyncio.Event`.
- A default label resolver looks up the active experiment when the runner does
  not supply one.

### `backend/db.py`

- Owns the SQLite schema and every query used by the API, runner and ML
  pipeline.
- `experiments` stores fault, target, start/end and `fixes_on`.
- `samples` stores one row per service per tick with `up`, `latency_ms`,
  `error` and `label`.
- `experiment_runs` stores phase timestamps, status, score, postmortem and
  error text.
- Connections use a 10 s timeout, `foreign_keys=ON` and WAL mode; writes are
  committed per context manager.
- Provides `start_experiment`, `end_experiment`, `insert_samples`,
  `samples_between`, `create_run`, `update_run`, `list_runs` and
  `run_detail`.
- `samples_for_experiment` feeds the detail endpoint and the ML dataset loader.

### `backend/runtime.py`

- Holds the pure helpers shared by the runner, API and tests.
- `derive_status()` returns `bad` for down/error, `warn` above 3x baseline and
  `ok` otherwise.
- `status_for_sample()`, `statuses_from_rows()` and `worst_status()` keep the
  most severe observation per service.
- `baseline_from_rows()` takes the median latency of successful baseline
  samples.
- `recent_metrics()` returns the latest gateway latency and the rolling error
  rate.
- `resilience_breakdown()` implements 100 - 15/failed - 6/degraded + 10
  containment bonus, clamped to 0-100.
- `phase_stats()` and `build_postmortem()` produce the per-phase evidence and
  the deterministic report text.

### `backend/ws.py`

- `EventHub` tracks connected WebSocket clients in a set.
- `connect()` accepts the socket and registers it; `disconnect()` removes it.
- `broadcast()` sends one JSON event to every client.
- Sockets that fail during a send are dropped instead of breaking the run.
- `log()` is a convenience wrapper for `{"type": "log", "level", "text"}`.
- `connection_count` is exposed by `/health` for quick diagnostics.

### `backend/chaos/engine.py`

- Applies and clears the three supported faults and always returns a result
  dict.
- `latency()` and `memory()` post to `/_chaos/latency` and `/_chaos/memory` on
  the target service, so they work without Docker.
- `reset_all()` posts `/_chaos/reset` to every service.
- `kill()` and `restore()` use the Docker SDK, resolving containers by compose
  project label and falling back to `{project}-{service}`.
- Missing Docker is reported as an `ok: false` error with the exception type.
- Unknown service names are rejected before any network or Docker call.

## ML pipeline

### `backend/ml/features.py`

- Defines the 10-feature vector: five per-service and five aggregated
  dependency features.
- `affected_services(target)` walks callers upstream to define the blast radius
  used by labels and scoring.
- Windows are 5 s long with a minimum of 3 samples.
- `base_features()` computes mean/max latency, error rate, up ratio and a
  least-squares latency slope.
- `_dependency_features()` aggregates each service's direct dependencies into a
  fixed-length block.
- `_label_window()` marks only the target and its callers positive during a
  fault; unrelated services stay hard negatives.
- Recovery and ambiguous ramp windows are excluded instead of being labelled.
- `build_windows()` returns `Window` objects with service, span, phase, run id
  and features.

### `backend/ml/data.py`

- Loads a dataset database into a frozen `Dataset` with samples, runs and
  metadata.
- Reads `samples`, joins `experiments` with `experiment_runs`, and reads the
  `ml_meta` key/value table.
- Creates `ml_meta` if an older database does not have it.
- `write_metadata()` stores generator source, seed, plan and phase lengths so a
  metrics file can state provenance.
- Kept deliberately read-only so training cannot mutate the raw telemetry.

### `backend/ml/simulate.py`

- Generates deterministic telemetry for Docker-less dataset builds.
- Mirrors the six-service topology, dependencies and phase labels of the real
  runner.
- Uses 5 s baseline, 10 s fault and 5 s recovery with a 1 s experiment gap.
- Baseline latencies and fault effects are fixed constants, so runs are
  reproducible.
- `build_experiment_plan()` covers the fault/target matrix; the generator adds
  healthy-only traffic.
- `write_simulated_dataset()` writes rows through the normal `ChaosDatabase`
  schema.

### `backend/ml/scripts/generate_dataset.py`

- CLI dataset generator used by the Phase 5 pipeline.
- `--source stack` runs real experiments against Compose and records healthy
  traffic.
- `--source simulated` uses `ml/simulate.py`; `auto` prefers the stack and
  falls back to simulation.
- Always starts from a fresh database, removing stale WAL/SHM files.
- Writes `backend/data/ml_dataset.db` by default and records provenance in
  `ml_meta`.
- Run from `backend/`: `python -m ml.scripts.generate_dataset --source auto`.

### `backend/ml/train.py`

- Trains the Isolation Forest on healthy training windows only.
- Holds out whole experiments by fault type and rotates targets across train,
  validation and test.
- Healthy-only windows are split by time with a 5 s purge gap.
- Fits `IsolationForest(n_estimators=200, contamination=0.02,
  random_state=42)`.
- Calibrates raw decision scores to 0-1 and chooses the threshold on validation
  F1.
- Writes `backend/models/isolation_forest.joblib`, `docs/model_metrics.json`
  and `docs/confusion_matrix.png`.
- Emits provenance and recommendations alongside the metrics.

### `backend/ml/evaluate.py`

- Pure evaluation helpers with no model dependency.
- `binary_metrics()` computes TP/FP/FN/TN, precision, recall, F1, accuracy,
  specificity and support.
- `choose_threshold()` sweeps candidate thresholds on the validation split and
  maximises F1.
- `evaluate_windows()` adds score quantiles and per-fault recall.
- `print_report()`, `recommendations()` and `write_json()` produce the human
  and machine-readable outputs.
- The published test split reports precision 0.9774, recall 0.9611 and F1
  0.9692.

### `backend/ml/detector.py`

- `AnomalyDetector` wraps the trained model plus calibration and threshold.
- `load()` reads the joblib artifact and applies safe defaults when metadata is
  missing.
- `score()` accepts a `Window`, a mapping or a feature sequence and returns a
  calibrated 0-1 value.
- The threshold comes from validation F1 (`0.5719` in the published run).
- `is_anomaly()` is a thin comparison used by callers and tests.
- Missing artifacts raise on `load()`; callers treat that as "no model" and
  fall back.

### `backend/ml/plotting.py`

- Renders `docs/confusion_matrix.png` with matplotlib's `Agg` backend.
- Uses the project's dark palette and a teal colormap.
- Prints counts and row shares in each cell.
- Labels axes as actual/predicted `normal`/`fault`.
- Titles the figure with the threshold and F1 score.
- Creates the output directory if needed and closes the figure afterwards.

## Agent

### `backend/agent/service.py`

- `AgentService` coordinates the planner, tools and postmortem writer.
- `status()` reports provider, model and `llm`/`fallback` mode without exposing
  a key.
- `plan()` logs `get_topology()` and the chosen plan, then returns an
  `ExperimentPlan`.
- Lifecycle hooks log agent observations during start, baseline, fault and
  recovery.
- The baseline hook summarises per-service latency and reads logs for abnormal
  services.
- `finish()` builds the grounded context and streams the postmortem word count.
- All hooks are awaited by the runner through a guarded `_agent_step()`.

### `backend/agent/planner.py`

- Asks the LLM for one safe experiment and validates the JSON response.
- The system prompt restricts faults to kill/latency/memory and targets to
  topology node ids.
- Hypotheses are limited to one sentence of at most 25 words.
- Two invalid or failed attempts fall back to `rule_based_plan()`.
- The rule chooses `latency` on the service with the most direct callers.
- `source` distinguishes `llm` from `rule` in the API response.
- `plan_experiment()` is a convenience wrapper for scripts and tests.

### `backend/agent/postmortem.py`

- `PostmortemWriter` turns evidence into a short structured report.
- The LLM prompt asks for exactly `root_cause`, `blast_radius` and `fixes`.
- Text is clipped to 35 words for the cause, 25 for the blast radius, 15 per
  fix and 120 words overall.
- Missing or invalid JSON falls back to a deterministic template.
- The template derives cause, impact and three fixes from the fault and
  affected services.
- The rendered text is `Root cause: ... Blast radius: ... Fixes: 1) ...`.
- `source` is `llm` or `template`, matching the WebSocket payload.

### `backend/agent/llm.py`

- Builds the configured LLM client once through `core.config` and
  `core.agent.llm.build_client`.
- A broken provider configuration returns `None`, which selects fallback mode.
- `extract_json_object()` strips markdown fences and finds the outermost JSON
  object.
- Raises `ValueError` for missing, non-object or malformed JSON.
- Keeps provider traffic in the backend so no key reaches the browser.

### `backend/agent/context.py`

- Assembles the compact evidence sent to the postmortem LLM.
- Computes baseline latency from successful pre-fault samples.
- Derives the phase of every sample from the run's fault timestamps.
- Builds a per-service status timeline and the affected-service list.
- Scores the fault window with the Phase 5 detector when available.
- Includes experiment metadata, phase statistics and fixes state.
- Keeps the payload small enough for a local model.

### `backend/agent/tools.py`

- Synchronous tools that an LLM or test can call directly.
- `get_topology()` returns the same graph as `GET /topology`.
- `inject_fault()` dispatches kill/latency/memory through the chaos engine.
- `read_metrics()` summarises sample count, mean/max latency, error rate, up
  ratio and the latest sample.
- `read_logs()` derives failure and latency-spike lines from samples because
  the stack has no log shipper.
- `rollback()` resets HTTP faults and restores every container.
- Unknown services return `ok: false` instead of raising.

### `backend/agent/models.py`

- Pydantic schemas shared by the planner, writer and API.
- `ExperimentPlan` validates fault, target, hypothesis, optional value and
  `llm`/`rule` source.
- A field validator trims the hypothesis to one sentence and adds terminal
  punctuation.
- A model validator fills default values when the model omits them.
- `PostmortemDraft` is the JSON shape requested from the LLM.
- `Postmortem` adds rendered text, word count and `llm`/`template` source.

## Frontend

### `frontend/src/App.tsx`

- Top-level layout: `TopBar`, service map, control panel, live metrics, agent
  console, postmortem and compare panel.
- Calls `useWebSocket()` once to start the live stream.
- In `?mock=1` mode, starts the scripted experiment after a short delay.
- Uses a responsive grid that collapses to one column on small screens.
- Renders the scanline overlay and the sticky header around the dashboard.

### `frontend/src/store/useChaosStore.ts`

- Zustand store for all dashboard state and actions.
- Holds topology, services, logs, metrics, anomaly scores, score breakdown,
  postmortem and compare outcomes.
- `ingest()` routes each WebSocket event type into the right slice and caps the
  log/metric buffers.
- `runExperiment()` posts to the API or starts the mock script; `runAgentExperiment()`
  requests a plan first.
- Tracks `running`, `planning`, `backendDown` and `lastError` for the UI.
- Seeds compare state from experiment history and updates it on each
  postmortem by the fixes flag.
- `bootstrap()` checks `/health`, then loads topology and history.

### `frontend/src/lib/api.ts`

- Typed REST client for `/health`, `/topology`, `/agent/plan`,
  `/agent/status`, `/experiments` and `/experiments/{id}`.
- `ApiError` carries the HTTP status; status `0` means a network failure and is
  rendered as "backend unreachable".
- Reads only public `VITE_API_BASE_URL`; empty means same origin through the
  Vite proxy.
- Parses JSON error bodies and keeps a readable fallback message.
- `resolveWsUrl()` prefers `?ws=`, then `VITE_WS_URL`, then same-origin `/ws`.

### `frontend/src/types/chaos.ts`

- Shared TypeScript types for the whole dashboard.
- Defines service status, fault kinds, log levels and connection states.
- Models every WebSocket event: state, log, metrics, anomaly, score and
  postmortem.
- Adds API shapes for topology, experiments, agent plans and status.
- Defines the compare run outcome and override types.

### `frontend/src/hooks/useWebSocket.ts`

- Keeps one WebSocket open and feeds frames into the store.
- Bootstraps health/topology/history once per page load.
- Reconnects with exponential backoff from 1 s up to 8 s.
- Ignores malformed frames rather than breaking the stream.
- Re-announces "live" and refreshes topology/history after reconnecting.
- Leaves the dashboard usable and shows an offline banner when the backend is
  down.

### `frontend/src/hooks/useAnimation.ts`

- `useCountUp()` eases a displayed number toward its target with an
  ease-out cubic curve.
- The gauge uses it so score changes animate instead of jumping.
- `useTypewriter()` reveals text character by character and reports `typing`.
- The typewriter restarts from zero whenever the text or speed changes.
- Both clean up their timers on unmount or value changes.

### `frontend/src/components/Panel.tsx`

- Shared HUD panel chrome used by every dashboard section.
- Renders a title, optional code label and optional action slot.
- Adds four corner brackets and a bordered header.
- Accepts custom class names for the outer panel and the body.
- Keeps layout handling (min-width, flex) consistent across panels.

### `frontend/src/components/TopBar.tsx`

- Sticky header with logo, connection badge, fixes toggle and clock.
- The connection badge maps live/connecting/offline/mock to colour and text.
- `FixesToggle` is a switch that is disabled while an experiment runs.
- Shows a red banner when the backend is unreachable, with start instructions.
- The clock updates every second and uses the local timezone.

### `frontend/src/components/ServiceMap.tsx`

- React Flow view of the six services and their call edges.
- Nodes show status colour, latency and the selected target.
- Edge colour and animation follow the worst status of the two endpoints.
- Uses a fixed layout from `lib/topology.ts` so first paint matches the API.
- Shows a "no live link" hint with the `?mock=1` escape hatch.
- Includes a legend and non-interactive controls.

### `frontend/src/components/LiveMetrics.tsx`

- Resilience gauge plus p95 latency, error rate and anomaly stats.
- Computes p95 from the last 60 metric samples.
- Renders a Recharts line chart of latency and error rate.
- Colour thresholds turn stats amber/red as error rate, latency or anomaly
  rises.
- Footer summarises failed/degraded counts and containment from the score
  breakdown.

### `frontend/src/components/ResilienceGauge.tsx`

- Animated SVG gauge for the 0-100 resilience score.
- Draws an arc with tick marks and a score-progress arc.
- Uses `useCountUp()` so score changes animate.
- Colour and verdict come from `scoreColor()` and `scoreVerdict()`.
- Includes an accessible `role="img"` label with the rounded score.

### `frontend/src/components/ControlPanel.tsx`

- Fault and target selectors with hints and the target role.
- RUN button posts the selected experiment and shows a running state.
- AGENT MODE requests a plan, displays fault/target/hypothesis/source, then
  runs it.
- Past experiments load their stored postmortem when clicked.
- Shows the last error inline and disables controls while busy.
- Displays the 10 s / 20 s / 10 s phase legend.

### `frontend/src/components/ComparePanel.tsx`

- Compares the last run with fixes off against the last run with fixes on.
- Each card shows score, run id, fault/target, relative time and a progress bar.
- The header shows the score delta between the two runs.
- Explains when one side is missing instead of rendering misleading numbers.
- Footer restates the resilience formula.
- Reads state seeded from experiment history and updated on each postmortem.

### `frontend/src/components/AgentConsole.tsx`

- Auto-scrolling, colour-coded event log.
- `info`, `success`, `warn` and `error` levels get distinct tags and colours.
- Each line shows clock time, level tag and text.
- Shows an idle empty state before the first experiment.
- Scrolls to the newest line when the log grows.

### `frontend/src/components/PostmortemPanel.tsx`

- Typewriter view of the latest postmortem.
- Shows `typing` / `complete` / `standby` state in the header.
- After typing finishes, shows chips for grounding, source, score and the
  no-secrets boundary.
- Shows "collecting evidence" while a run is active and "no report yet"
  otherwise.
- Reads text and source from the store.

### `frontend/src/mock/script.ts`

- Scripted replay for `?mock=1`, emitting the same event shapes as the backend.
- Compressed timeline: baseline, fault with a short failure burst, recovery,
  then postmortem.
- Derives blast radius from the topology's reverse callers.
- Computes statuses, anomaly scores and the resilience breakdown locally.
- Emits state, metrics, anomaly, score, log and postmortem frames.
- Keeps the mock plan and history consistent with the UI controls.

### `frontend/src/lib/stats.ts`

- Small numeric and formatting helpers with no dependencies.
- `clamp`, `percentile` and `mean` back the charts and stat tiles.
- `formatLatency` switches between ms and seconds.
- `formatPercent`, `formatClock` and `formatRelative` keep labels consistent.
- `mean` is available for the same rolling windows and returns `null` when empty.

### `frontend/src/lib/theme.ts`

- Central colour map for statuses (`ok`/`warn`/`bad`) and charts.
- `scoreColor()` thresholds score colour at 80 and 50.
- `scoreVerdict()` maps the same thresholds to nominal/degraded/critical.
- Keeps Tailwind class colours and SVG colours in sync.
- `COLORS` also exposes muted, cyan, mint, amber and red for charts and gauges.

### `frontend/src/lib/topology.ts`

- Mirrors `backend/topology.py` for first paint and offline fallback.
- Declares the six nodes with ports and roles plus the six edges.
- Provides fixed node positions for a readable caller-left/callee-right layout.
- `positionFor()` falls back to a grid for unknown nodes.
- `callersOf()` derives direct callers from the edge list.

## Sample stack

### `sample-stack/docker-compose.yml`

- Six FastAPI services on one Compose network, project name from
  `COMPOSE_PROJECT_NAME`.
- Shared anchors add the optional `../.env`, `restart: unless-stopped` and a
  `/health` healthcheck to every service.
- `depends_on` uses `condition: service_healthy`, so startup order follows the
  topology.
- Host ports are `${GATEWAY_PORT:-8000}` through `${DB_PORT:-8005}`.
- `RESILIENT` is passed to every service from `.env` and defaults to `false`.
- No credentials are written in the file; values are `${VAR}` references only.

### `sample-stack/services/common/service_base.py`

- Shared harness that builds each service's FastAPI app.
- Tracks p50 latency, request count and error rate per process.
- `ChaosState` holds injected latency and resident memory blocks.
- Middleware applies latency before the request and records response time.
- Exposes `/health`, `/metrics` and `/_chaos/latency|memory|reset`.
- Reports `resilient`, timeout, retry count and circuit-breaker state in
  `/health`.
- A dependency-error handler returns a structured `502` in fragile mode.

### `sample-stack/services/common/http_client.py`

- Shared dependency client with a deliberately fragile default.
- Default mode: one attempt, 5 s timeout, no circuit breaker, raise on failure.
- `RESILIENT=true`: one retry, 1 s timeout, 3-failure circuit breaker with a
  10 s cooldown and caller-supplied fallbacks.
- Every service uses it, so fixes-on and fixes-off are comparable.
- Returns `{"degraded": True, ...}` fallbacks instead of exceptions in
  resilient mode.

### `sample-stack/services/gateway/app.py`

- Public entry point; calls auth `/verify` then orders `/create`.
- Returns `ok` or `degraded` based on either dependency.
- Provides fallbacks for both calls when resilient mode is on.
- `/checkout` is the synthetic user path the collector measures.
- It is the only service the Compose file publishes as the public entry point.

### `sample-stack/services/auth/app.py`

- Verifies a demo session by reading `session:demo` from the cache.
- Writes the default user to the cache on a miss when the cache is healthy.
- Reports `verified`, `user`, `cached` and `degraded`.
- Cache failures degrade the response rather than crashing the service.
- The demo session key is `session:demo` and the default user is `user-42`.

### `sample-stack/services/orders/app.py`

- Creates an order id and charges payments.
- Persists the order through the db service.
- Returns `created` or `degraded` based on both dependencies.
- `ORDER_AMOUNT` and dependency URLs are environment-driven.
- Order ids use `ord_` plus ten hex characters; the demo amount is 42.50.

### `sample-stack/services/payments/app.py`

- Simulates a charge and writes the record to db.
- Returns `captured` or `captured_unpersisted` when persistence degrades.
- Validates the amount is greater than zero.
- Charge and order ids are randomly generated per request.
- Charge ids use `ch_` plus twelve hex characters.

### `sample-stack/services/cache/app.py`

- In-memory key/value store exposed over `/cache/{key}`.
- `GET` reports `found` and the value; `POST` stores it.
- State is per-process and intentionally non-durable.
- Used by auth for session verification.
- `CACHE` is a module-level `dict[str, str]`; keys are returned as requested.

### `sample-stack/services/db/app.py`

- In-memory table store exposed over `/records/{table}/{key}`.
- `POST` stores arbitrary JSON values; `GET` reads them back.
- `/tables/{table}` lists up to the last 50 keys and the row count.
- Used by orders and payments and intentionally non-durable.
- `TABLES` is a nested module-level dict keyed by table and then record key.

## Tooling and scripts

### `scripts/check_secrets.py`

- Dependency-free second line of defence behind gitleaks.
- Blocks staged `.env*`, `*.pem`, `*.key`, `*.p12`, `*.pfx` and database files.
- Scans for private-key markers, AWS/GitHub/Slack/Google token patterns and
  hardcoded credential assignments.
- Works on `git diff --cached` so it only inspects what is being committed.
- Fails closed: placeholders are the documented way to clear a false positive.
- Excludes itself from the scan so its pattern fragments do not self-trigger.

### `backend/scripts/smoke_test.py`

- Phase 2 end-to-end smoke test against an already-running sample stack.
- Starts the collector, records a baseline, injects latency and resets it.
- Reads gateway latency back from SQLite for baseline/fault/recovery.
- Fails unless the fault p50 jumps by at least `--min-jump-ms` (default 800 ms).
- Does not need Docker itself because latency is applied over HTTP.
- Default DB is `backend/data/smoke.db`.

### `backend/scripts/ws_client.py`

- Minimal WebSocket client for the live stream.
- Connects to `ws://127.0.0.1:8090/ws` and can start an experiment by REST.
- Prints every event until a postmortem arrives.
- Flags cover fault, target, fixes, `--no-run` and an overall timeout.
- Exits 0 only when a postmortem was received.

### `run_demo.sh` and `run_demo.ps1`

- One-command startup scripts for macOS/Linux and Windows.
- Create `.env` from `.env.example` when missing.
- Create the backend virtualenv if needed and install Python/Node dependencies.
- Start the Compose stack, wait for gateway health, then start the API.
- Wait for `/health` before starting the dashboard.
- Print the dashboard and API-docs URLs at the end.
- The shell script traps Ctrl+C to stop the backend it started.

### `backend/tests/`

- Pytest suite covering the API/WebSocket lifecycle, runtime scoring, stack
  restarts, chaos engine, collector, SQLite, ML features/training/detector and
  the agent planner/postmortem.
- Tests use fakes for Docker, the collector and the LLM, so they run offline.
- Phase 3 tests assert the exact `score` event shape and the formula results.
- Agent tests cover valid plans, invalid JSON and fallback text.
- Run from `backend/`: `pytest -q`.
