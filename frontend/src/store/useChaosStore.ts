import { create } from "zustand";
import { api, ApiError, resolveWsUrl } from "../lib/api";
import { DEFAULT_TOPOLOGY } from "../lib/topology";
import { clamp } from "../lib/stats";
import { startMockExperiment, type MockHandle } from "../mock/script";
import type {
  AgentPlan,
  ConnectionState,
  ExperimentSummary,
  FaultKind,
  LogLevel,
  LogLine,
  MetricSample,
  RunOutcome,
  RunOverrides,
  ScoreBreakdown,
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
  planning: boolean;
  activeExperimentId: number | null;
  runStartedAt: number | null;
  fault: FaultKind;
  target: string;
  applyFixes: boolean;
  agentPlan: AgentPlan | null;
  experiments: ExperimentSummary[];
  compareOff: RunOutcome | null;
  compareOn: RunOutcome | null;

  setConnection: (state: ConnectionState) => void;
  setFault: (fault: FaultKind) => void;
  setTarget: (target: string) => void;
  setApplyFixes: (enabled: boolean) => void;
  ingest: (event: WsEvent) => void;
  runExperiment: (overrides?: RunOverrides) => Promise<void>;
  runAgentExperiment: () => Promise<void>;
  loadTopology: () => Promise<void>;
  refreshExperiments: () => Promise<void>;
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
  planning: false,
  activeExperimentId: null,
  runStartedAt: null,
  fault: "latency",
  target: "payments",
  applyFixes: false,
  agentPlan: null,
  experiments: MOCK_MODE ? MOCK_EXPERIMENTS : [],
  compareOff: MOCK_MODE ? outcomeFor(MOCK_EXPERIMENTS[2]) : null,
  compareOn: MOCK_MODE ? outcomeFor(MOCK_EXPERIMENTS[0]) : null,

  setConnection: (connection) =>
    set((state) => ({
      connection,
      backendDown:
        connection === "offline" ? true : connection === "connecting" ? state.backendDown : false,
      lastError:
        connection === "live" && state.backendDown ? null : state.lastError,
    })),

  setFault: (fault) => set({ fault }),
  setTarget: (target) => set({ target }),
  setApplyFixes: (applyFixes) => set({ applyFixes }),

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
      fault: state.fault,
      target: state.target,
      fixes: state.applyFixes,
      score,
      at: finishedAt,
    };
    set({
      postmortem: event.text,
      postmortemSource: event.source ?? (event.structured ? "llm" : "template"),
      running: false,
      planning: false,
      activeExperimentId: null,
      ...(state.applyFixes ? { compareOn: outcome } : { compareOff: outcome }),
    });

    if (state.mockMode) {
      const summary: ExperimentSummary = {
        id: finishedId ?? ++mockId,
        fault: state.fault,
        target: state.target,
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

  runExperiment: async (overrides) => {
    if (get().running || get().planning) return;

    const mockMode = get().mockMode;
    const fault = overrides?.fault ?? get().fault;
    const target = overrides?.target ?? get().target;
    const applyFixes = overrides?.fixes ?? get().applyFixes;
    const startedAt = Date.now();
    const experimentId = mockMode ? ++mockId : null;

    set({
      running: true,
      fault,
      target,
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
      text: `operator request // ${fault} -> ${target} // fixes ${applyFixes ? "on" : "off"}`,
    });

    if (mockMode) {
      mockHandle?.stop();
      mockHandle = startMockExperiment({
        fault,
        target,
        fixes: applyFixes,
        emit: (event) => get().ingest(event),
        onFinished: () => {
          mockHandle = null;
        },
      });
      return;
    }

    try {
      const run = await api.runExperiment({ fault, target, fixes: applyFixes });
      set({ activeExperimentId: run.id, backendDown: false });
      get().ingest({
        type: "log",
        level: "success",
        text: `experiment #${run.id} accepted // streaming telemetry`,
      });
      void get().refreshExperiments();
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

  runAgentExperiment: async () => {
    if (get().running || get().planning) return;

    set({ planning: true, lastError: null });
    get().ingest({
      type: "log",
      level: "info",
      text: "agent mode // selecting the next experiment",
    });

    try {
      const plan: AgentPlan = get().mockMode
        ? {
            fault: "latency",
            target: "db",
            hypothesis:
              "db has the most callers, so delaying it should show how a local stall propagates.",
            value: 2_000,
            source: "rule",
          }
        : await api.agentPlan();

      set({ planning: false, agentPlan: plan, backendDown: false });
      get().ingest({
        type: "log",
        level: "success",
        text: `agent plan // ${plan.fault} -> ${plan.target} // ${plan.source}`,
      });
      get().ingest({
        type: "log",
        level: "info",
        text: `agent hypothesis // ${plan.hypothesis}`,
      });
      await get().runExperiment({ fault: plan.fault, target: plan.target });
    } catch (error) {
      const message = errorMessage(error, "agent planner unavailable");
      set({
        planning: false,
        lastError: message,
        backendDown: error instanceof ApiError && error.status === 0,
      });
      get().ingest({
        type: "log",
        level: "error",
        text: `agent mode failed // ${message}`,
      });
    }
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
      set({ backendDown: false, lastError: null });
    } catch (error) {
      const message = errorMessage(error, "backend unreachable");
      set({ backendDown: true, lastError: message });
      get().ingest({
        type: "log",
        level: "warn",
        text: `backend offline // ${message} // retrying in the background`,
      });
      return;
    }

    await Promise.all([get().loadTopology(), get().refreshExperiments()]);
  },
}));
