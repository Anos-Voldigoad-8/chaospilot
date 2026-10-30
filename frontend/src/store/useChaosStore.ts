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
  topology: Topology;
  services: Record<string, ServiceRuntime>;
  logs: LogLine[];
  metrics: MetricSample[];
  score: number;
  postmortem: string;
  running: boolean;
  activeExperimentId: number | null;
  runStartedAt: number | null;
  fault: FaultKind;
  target: string;
  applyFixes: boolean;
  experiments: ExperimentSummary[];

  setConnection: (state: ConnectionState) => void;
  setFault: (fault: FaultKind) => void;
  setTarget: (target: string) => void;
  setApplyFixes: (enabled: boolean) => void;
  ingest: (event: WsEvent) => void;
  runExperiment: () => Promise<void>;
  loadTopology: () => Promise<void>;
  refreshExperiments: () => Promise<void>;
  loadExperiment: (id: number) => Promise<void>;
  bootstrap: () => Promise<void>;
}

export const useChaosStore = create<ChaosState>((set, get) => ({
  mockMode: MOCK_MODE,
  connection: MOCK_MODE ? "mock" : "connecting",
  topology: DEFAULT_TOPOLOGY,
  services: zeroedServices(),
  logs: [],
  metrics: [],
  score: 100,
  postmortem: "",
  running: false,
  activeExperimentId: null,
  runStartedAt: null,
  fault: "latency",
  target: "payments",
  applyFixes: false,
  experiments: MOCK_MODE ? MOCK_EXPERIMENTS : [],

  setConnection: (connection) => set({ connection }),

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

    if (event.type === "score") {
      set({ score: clamp(event.value, 0, 100) });
      return;
    }

    const finishedAt = Date.now();
    const finishedId = get().activeExperimentId;
    set({ postmortem: event.text, running: false, activeExperimentId: null });

    if (get().mockMode) {
      const { fault, target, applyFixes, score, runStartedAt } = get();
      const summary: ExperimentSummary = {
        id: finishedId ?? ++mockId,
        fault,
        target,
        fixes: applyFixes,
        status: "completed",
        score: Math.round(score),
        started: runStartedAt ?? finishedAt - 15_000,
        ended: finishedAt,
        sample_count: 180,
        error_count: 0,
      };
      set((state) => ({
        experiments: [summary, ...state.experiments.filter((run) => run.id !== summary.id)].slice(
          0,
          12,
        ),
      }));
      return;
    }

    void get().refreshExperiments();
  },

  runExperiment: async () => {
    if (get().running) return;

    const { mockMode, fault, target, applyFixes } = get();
    const startedAt = Date.now();
    const experimentId = mockMode ? ++mockId : null;

    set({
      running: true,
      activeExperimentId: experimentId,
      runStartedAt: startedAt,
      postmortem: "",
      metrics: [],
      score: 100,
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
      set({ activeExperimentId: run.id });
      get().ingest({
        type: "log",
        level: "success",
        text: `experiment #${run.id} accepted // streaming telemetry`,
      });
      void get().refreshExperiments();
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "backend rejected the experiment";
      set({ running: false, activeExperimentId: null });
      get().ingest({ type: "log", level: "error", text: `run failed // ${message}` });
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
      set({ experiments });
    } catch {
      // History is best-effort; the live stream still drives the dashboard.
    }
  },

  loadExperiment: async (id) => {
    get().ingest({ type: "log", level: "info", text: `loading report #${id}` });

    if (get().mockMode) {
      const run = get().experiments.find((item) => item.id === id);
      if (run) set({ postmortem: mockReport(run) });
      return;
    }

    try {
      const detail = await api.experiment(id);
      set({ postmortem: detail.postmortem ?? "" });
    } catch {
      get().ingest({ type: "log", level: "error", text: `report #${id} unavailable` });
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
    await Promise.all([get().loadTopology(), get().refreshExperiments()]);
  },
}));
