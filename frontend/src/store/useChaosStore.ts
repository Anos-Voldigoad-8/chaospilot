import { create } from "zustand";
import { api, ApiError, resolveWsUrl } from "../lib/api";
import { DEFAULT_TOPOLOGY } from "../lib/topology";
import { clamp } from "../lib/stats";
import { startMockExperiment, type MockHandle } from "../mock/script";
import type {
  ConnectionState,
  ExperimentSummary,
  FaultKind,
  LogLevel,
  LogLine,
  MetricSample,
  RunOutcome,
  ScoreBreakdown,
  Scenario,
  ServiceRuntime,
  Topology,
  WsEvent,
} from "../types/chaos";

const MAX_LOGS = 220;
const MAX_METRICS = 120;

const MOCK_MODE =
  new URLSearchParams(window.location.search).get("mock") === "1" ||
  import.meta.env.VITE_MOCK === "1";

let logSeq = 0;
let mockHandle: MockHandle | null = null;
let mockId = 105;

const MOCK_STARTED_AT = Date.now();
const MOCK_EXPERIMENTS: ExperimentSummary[] = [
  {
    id: 104,
    fault: "memory",
    target: "db",
    fixes: true,
    status: "completed",
    score: 72,
    started: MOCK_STARTED_AT - 42 * 60_000,
    ended: MOCK_STARTED_AT - 41 * 60_000,
    sample_count: 246,
    error_count: 0,
  },
  {
    id: 103,
    fault: "kill",
    target: "cache",
    fixes: false,
    status: "completed",
    score: 51,
    started: MOCK_STARTED_AT - 128 * 60_000,
    ended: MOCK_STARTED_AT - 127 * 60_000,
    sample_count: 240,
    error_count: 18,
  },
  {
    id: 102,
    fault: "latency",
    target: "payments",
    fixes: false,
    status: "completed",
    score: 40,
    started: MOCK_STARTED_AT - 6 * 3_600_000,
    ended: MOCK_STARTED_AT - 6 * 3_600_000 + 42_000,
    sample_count: 240,
    error_count: 0,
  },
  {
    id: 101,
    fault: "latency",
    target: "auth",
    fixes: true,
    status: "completed",
    score: 63,
    started: MOCK_STARTED_AT - 26 * 3_600_000,
    ended: MOCK_STARTED_AT - 26 * 3_600_000 + 44_000,
    sample_count: 252,
    error_count: 2,
  },
];

const MOCK_SCENARIOS: Scenario[] = [
  {
    id: 1,
    fault_type: "latency",
    target_service: "payments",
    duration_minutes: 15,
    severity: "high",
    load_curve: [],
    source: "seed",
    source_url: "scripts/build_seed.py",
    data_source: "seed",
    title: "seed latency on payments",
    created_at: MOCK_STARTED_AT - 10 * 60_000,
  },
  {
    id: 2,
    fault_type: "kill",
    target_service: "db",
    duration_minutes: 30,
    severity: "critical",
    load_curve: [],
    source: "seed",
    source_url: "scripts/build_seed.py",
    data_source: "seed",
    title: "seed database crash",
    created_at: MOCK_STARTED_AT - 20 * 60_000,
  },
];

function zeroedServices(): Record<string, ServiceRuntime> {
  return Object.fromEntries(
    DEFAULT_TOPOLOGY.nodes.map((node) => [
      node.id,
      { status: "ok", latency_ms: 0 } satisfies ServiceRuntime,
    ]),
  );
}

function freshBreakdown(value = 100): ScoreBreakdown {
  return { value, failed: [], degraded: [], contained: true, bonus: 0 };
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.status === 0
      ? `${error.message} // start it with run_demo.sh or run_demo.ps1`
      : error.message;
  }
  return fallback;
}

function outcomeFor(run: ExperimentSummary): RunOutcome | null {
  if (run.score === null) return null;
  return {
    id: run.id,
    fault: run.fault as FaultKind,
    target: run.target,
    fixes: run.fixes,
    score: Math.round(run.score),
    at: run.ended ?? run.started,
  };
}

function compareFromHistory(experiments: ExperimentSummary[]): {
  compareOff: RunOutcome | null;
  compareOn: RunOutcome | null;
} {
  const off = experiments.find((run) => !run.fixes && run.score !== null);
  const on = experiments.find((run) => run.fixes && run.score !== null);
  return {
    compareOff: off ? outcomeFor(off) : null,
    compareOn: on ? outcomeFor(on) : null,
  };
}

function mockReport(run: ExperimentSummary): string {
  const fault = run.fault === "kill" ? 340 : run.fault === "memory" ? 760 : 2_080;
  return [
    `Experiment #${run.id}: injected ${run.fault} on ${run.target} (fixes=${run.fixes ? "on" : "off"}).`,
    `Baseline: gateway p50 66ms, errors 0/10.`,
    `Fault: gateway p50 ${fault}ms, errors ${run.error_count ?? 0}/20.`,
    `Recovery: gateway p50 68ms, errors 0/10.`,
    `Gateway latency moved +${fault - 66}ms during the fault.`,
    `Resilience score: ${run.score ?? 0}/100.`,
  ].join(" ");
}

function normalizeLevel(level: string): LogLevel {
  if (level === "warn" || level === "error" || level === "success") return level;
  return "info";
}

interface ChaosState {
  mockMode: boolean;
  connection: ConnectionState;
  backendDown: boolean;
  lastError: string | null;

  topology: Topology;
  services: Record<string, ServiceRuntime>;
  logs: LogLine[];
  metrics: MetricSample[];
  anomaly: number;
  anomalyServices: Record<string, number>;

  score: number;
  scoreBreakdown: ScoreBreakdown;
  postmortem: string;
  postmortemSource: "llm" | "template" | null;

  running: boolean;
  faultActive: boolean;
  collecting: boolean;
  activeExperimentId: number | null;
  runStartedAt: number | null;
  applyFixes: boolean;
  selectedScenarioId: number | null;
  scenarios: Scenario[];
  experiments: ExperimentSummary[];
  compareOff: RunOutcome | null;
  compareOn: RunOutcome | null;

  setConnection: (state: ConnectionState) => void;
  setApplyFixes: (enabled: boolean) => void;
  selectScenario: (id: number | null) => void;
  ingest: (event: WsEvent) => void;
  runExperiment: (overrides?: { scenario_id?: number; fixes?: boolean }) => Promise<void>;
  resolveExperiment: () => Promise<void>;
  stopExperiment: () => Promise<void>;
  collectData: () => Promise<void>;
  loadTopology: () => Promise<void>;
  refreshExperiments: () => Promise<void>;
  refreshScenarios: () => Promise<void>;
  loadExperiment: (id: number) => Promise<void>;
  bootstrap: () => Promise<void>;
}

export const useChaosStore = create<ChaosState>((set, get) => ({
  mockMode: MOCK_MODE,
  connection: MOCK_MODE ? "mock" : "connecting",
  backendDown: false,
  lastError: null,

  topology: DEFAULT_TOPOLOGY,
  services: zeroedServices(),
  logs: [],
  metrics: [],
  anomaly: 0,
  anomalyServices: {},

  score: 100,
  scoreBreakdown: freshBreakdown(),
  postmortem: "",
  postmortemSource: null,

  running: false,
  faultActive: false,
  collecting: false,
  activeExperimentId: null,
  runStartedAt: null,
  applyFixes: false,
  selectedScenarioId: MOCK_MODE ? MOCK_SCENARIOS[0].id : null,
  scenarios: MOCK_MODE ? MOCK_SCENARIOS : [],
  experiments: MOCK_MODE ? MOCK_EXPERIMENTS : [],
  compareOff: MOCK_MODE ? outcomeFor(MOCK_EXPERIMENTS[2]) : null,
  compareOn: MOCK_MODE ? outcomeFor(MOCK_EXPERIMENTS[0]) : null,

  setConnection: (connection) =>
    set((state) => ({
      connection,
      lastError:
        connection === "live" && state.backendDown ? null : state.lastError,
    })),

  setApplyFixes: (applyFixes) => set({ applyFixes }),

  selectScenario: (id) => set({ selectedScenarioId: id }),

  ingest: (event) => {
    if (event.type === "state") {
      set((state) => ({
        services: {
          ...state.services,
          [event.service]: {
            status: event.status,
            latency_ms: event.latency_ms,
          },
        },
      }));
      return;
    }

    if (event.type === "log") {
      const line: LogLine = {
        id: ++logSeq,
        at: Date.now(),
        level: normalizeLevel(event.level),
        text: event.text,
      };
      set((state) => ({ logs: [...state.logs, line].slice(-MAX_LOGS) }));
      return;
    }

    if (event.type === "metrics") {
      const sample: MetricSample = {
        t: Date.now(),
        latency: event.gateway_latency,
        errorRate: clamp(event.error_rate, 0, 1),
      };
      set((state) => ({ metrics: [...state.metrics, sample].slice(-MAX_METRICS) }));
      return;
    }

    if (event.type === "anomaly") {
      set({
        anomaly: clamp(event.value, 0, 1),
        anomalyServices: event.services,
      });
      return;
    }

    if (event.type === "score") {
      const value = clamp(event.value, 0, 100);
      set({
        score: value,
        scoreBreakdown: {
          value,
          failed: event.failed ?? [],
          degraded: event.degraded ?? [],
          contained: event.contained ?? true,
          bonus: event.bonus ?? 0,
        },
      });
      return;
    }

    const state = get();
    const finishedAt = Date.now();
    const finishedId = state.activeExperimentId;
    const score = Math.round(state.score);
    const outcome: RunOutcome = {
      id: finishedId,
      fault: "latency",
      target: state.selectedScenarioId
        ? state.scenarios.find((s) => s.id === state.selectedScenarioId)?.target_service ??
          "payments"
        : "payments",
      fixes: state.applyFixes,
      score,
      at: finishedAt,
    };
    set({
      postmortem: event.text,
      postmortemSource: event.source ?? (event.structured ? "llm" : "template"),
      running: false,
      faultActive: false,
      activeExperimentId: null,
      ...(state.applyFixes ? { compareOn: outcome } : { compareOff: outcome }),
    });

    if (state.mockMode) {
      const summary: ExperimentSummary = {
        id: finishedId ?? ++mockId,
        fault: "latency",
        target: outcome.target,
        fixes: state.applyFixes,
        status: "completed",
        score,
        started: state.runStartedAt ?? finishedAt - 15_000,
        ended: finishedAt,
        sample_count: 180,
        error_count: 0,
      };
      set((current) => ({
        experiments: [
          summary,
          ...current.experiments.filter((run) => run.id !== summary.id),
        ].slice(0, 12),
      }));
      return;
    }

    void get().refreshExperiments();
  },

  collectData: async () => {
    if (get().collecting) return;
    set({ collecting: true, lastError: null });
    get().ingest({
      type: "log",
      level: "info",
      text: "collect data // asking the agent to build scenarios from public sources",
    });

    try {
      const payload = await api.agentCollect();
      set({
        collecting: false,
        scenarios: payload.scenarios,
        backendDown: false,
        selectedScenarioId:
          payload.scenarios.length > 0
            ? payload.scenarios[0].id
            : get().selectedScenarioId,
      });
      get().ingest({
        type: "log",
        level: "success",
        text: `collected ${payload.count} scenarios // ready to run`,
      });
      const live = payload.scenarios.filter((s) => s.data_source === "live").length;
      const cached = payload.scenarios.filter((s) => s.data_source === "cached").length;
      const seed = payload.scenarios.filter((s) => s.data_source === "seed").length;
      get().ingest({
        type: "log",
        level: "info",
        text: `sources // live: ${live} cached: ${cached} seed: ${seed}`,
      });
    } catch (error) {
      const message = errorMessage(error, "data collection failed");
      set({ collecting: false, lastError: message, backendDown: error instanceof ApiError && error.status === 0 });
      get().ingest({ type: "log", level: "error", text: `collect failed // ${message}` });
    }
  },

  runExperiment: async (overrides) => {
    if (get().running || get().collecting) return;

    const mockMode = get().mockMode;
    const scenarioId = overrides?.scenario_id ?? get().selectedScenarioId;
    if (scenarioId == null) {
      set({ lastError: "no scenario selected" });
      return;
    }
    const applyFixes = overrides?.fixes ?? get().applyFixes;
    const scenario = get().scenarios.find((s) => s.id === scenarioId);
    const startedAt = Date.now();
    const experimentId = mockMode ? ++mockId : null;

    set({
      running: true,
      applyFixes,
      activeExperimentId: experimentId,
      runStartedAt: startedAt,
      postmortem: "",
      postmortemSource: null,
      metrics: [],
      anomaly: 0,
      anomalyServices: {},
      score: 100,
      scoreBreakdown: freshBreakdown(),
      lastError: null,
    });

    get().ingest({
      type: "log",
      level: "info",
      text: `run scenario #${scenarioId} // ${scenario?.fault_type} -> ${scenario?.target_service} // fixes ${applyFixes ? "on" : "off"}`,
    });

    if (mockMode) {
      mockHandle?.stop();
      mockHandle = startMockExperiment({
        fault: scenario?.fault_type ?? "latency",
        target: scenario?.target_service ?? "payments",
        fixes: applyFixes,
        emit: (event) => get().ingest(event),
        onFinished: () => {
          mockHandle = null;
        },
      });
      return;
    }

    try {
      const run = await api.runExperiment({ scenario_id: scenarioId, fixes: applyFixes });
      set({ activeExperimentId: run.id, backendDown: false, faultActive: true, running: true });
      get().ingest({
        type: "log",
        level: "success",
        text: `experiment #${run.id} accepted // streaming telemetry`,
      });
      void get().refreshExperiments();

      if (get().connection !== "live") {
        mockHandle?.stop();
        mockHandle = startMockExperiment({
          fault: (scenario?.fault_type as FaultKind) ?? "latency",
          target: scenario?.target_service ?? "payments",
          fixes: applyFixes,
          emit: (event) => get().ingest(event),
          onFinished: () => {
            mockHandle = null;
            void get().refreshExperiments();
          },
        });
      }
    } catch (error) {
      const message = errorMessage(error, "backend rejected the experiment");
      set({
        running: false,
        activeExperimentId: null,
        lastError: message,
        backendDown: error instanceof ApiError && error.status === 0,
      });
      get().ingest({ type: "log", level: "error", text: `run failed // ${message}` });
    }
  },

  resolveExperiment: async () => {
    const experimentId = get().activeExperimentId;
    if (experimentId == null) {
      set({ lastError: "no active experiment to resolve" });
      return;
    }
    set({ lastError: null });
    try {
      await api.resolveExperiment(experimentId);
      get().ingest({
        type: "log",
        level: "info",
        text: "fix applied // recovery phase started",
      });
    } catch (error) {
      const message = errorMessage(error, "failed to apply fix");
      set({
        lastError: message,
        backendDown: error instanceof ApiError && error.status === 0,
      });
      get().ingest({ type: "log", level: "error", text: `resolve failed // ${message}` });
    }
  },

  stopExperiment: async () => {
    const experimentId = get().activeExperimentId;
    if (experimentId == null) {
      set({ lastError: "no active experiment to stop" });
      return;
    }
    set({ lastError: null });
    try {
      await api.stopExperiment(experimentId);
    } catch (error) {
      // Best-effort: even if the API call fails, clear the local run state so
      // the operator can start a new task.
      const message = errorMessage(error, "failed to stop experiment");
      get().ingest({ type: "log", level: "warn", text: `stop requested // ${message}` });
    }
    // Reset the live run state so a new experiment can be started immediately.
    set({
      running: false,
      faultActive: false,
      activeExperimentId: null,
      runStartedAt: null,
      postmortem: "",
      postmortemSource: null,
      score: 100,
      scoreBreakdown: freshBreakdown(),
      metrics: [],
      anomaly: 0,
      anomalyServices: {},
      services: zeroedServices(),
      lastError: null,
    });
    get().ingest({
      type: "log",
      level: "info",
      text: "experiment stopped // ready for a new task",
    });
  },

  loadTopology: async () => {
    if (get().mockMode) return;
    try {
      const topology = await api.topology();
      if (topology.nodes.length > 0) set({ topology });
    } catch {
      // Keep the bundled topology; the map stays usable while the API is down.
    }
  },

  refreshExperiments: async () => {
    if (get().mockMode) return;
    try {
      const { experiments } = await api.experiments(12);
      const history = compareFromHistory(experiments);
      set((state) => ({
        experiments,
        compareOff: state.compareOff ?? history.compareOff,
        compareOn: state.compareOn ?? history.compareOn,
      }));
    } catch {
      // History is best-effort; the live stream still drives the dashboard.
    }
  },

  refreshScenarios: async () => {
    if (get().mockMode) return;
    try {
      const { scenarios } = await api.scenarios(50);
      set({ scenarios });
      if (scenarios.length > 0 && get().selectedScenarioId == null) {
        set({ selectedScenarioId: scenarios[0].id });
      }
    } catch {
      // Scenarios are best-effort; collect data to populate them.
    }
  },

  loadExperiment: async (id) => {
    get().ingest({ type: "log", level: "info", text: `loading report #${id}` });

    if (get().mockMode) {
      const run = get().experiments.find((item) => item.id === id);
      if (run) set({ postmortem: mockReport(run), postmortemSource: "template" });
      return;
    }

    try {
      const detail = await api.experiment(id);
      set({
        postmortem: detail.postmortem ?? "",
        postmortemSource: detail.postmortem ? "template" : null,
        ...(detail.score !== null
          ? { score: detail.score, scoreBreakdown: freshBreakdown(detail.score) }
          : {}),
      });
    } catch (error) {
      const message = errorMessage(error, `report #${id} unavailable`);
      get().ingest({ type: "log", level: "error", text: `report load failed // ${message}` });
    }
  },

  bootstrap: async () => {
    if (get().mockMode) {
      set({ connection: "mock" });
      get().ingest({
        type: "log",
        level: "success",
        text: `mock mode active // no backend required // ${resolveWsUrl()}`,
      });
      return;
    }

    try {
      await api.health();
      set({ backendDown: false, connection: "live", lastError: null });
    } catch (error) {
      const message = errorMessage(error, "backend unreachable");
      set({ backendDown: true, connection: "offline", lastError: message });
      get().ingest({
        type: "log",
        level: "warn",
        text: `backend offline // ${message} // retrying in the background`,
      });
      return;
    }

    await Promise.all([
      get().loadTopology(),
      get().refreshScenarios(),
      get().refreshExperiments(),
    ]);
  },
}));
