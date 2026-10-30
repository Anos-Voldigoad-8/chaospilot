import type { FaultKind, ServiceStatus, WsEvent } from "../types/chaos";
import { DEFAULT_TOPOLOGY } from "../lib/topology";
import { clamp } from "../lib/stats";

/**
 * Scripted experiment used by `?mock=1`. It emits exactly the same events as
 * the backend WebSocket, so every component works without a server.
 *
 * Timeline (compressed from 10s/20s/10s):
 *   0.0s – 3.6s   baseline
 *   3.6s – 10.6s  fault, with a short failure burst at 6.4s
 *   10.6s – 14.0s recovery
 *   14.5s         postmortem
 */

const BASELINE_END = 3_600;
const FAULT_END = 10_600;
const FINISH = 14_500;
const TICK = 400;
const BURST_START = 6_400;
const BURST_END = 8_200;

const BASELINE_LATENCY: Record<string, number> = {
  gateway: 66,
  auth: 12,
  orders: 15,
  cache: 7,
  payments: 8,
  db: 6,
};

const LATENCY_BY_DEPTH: Record<Exclude<FaultKind, "kill">, number[]> = {
  latency: [1_900, 2_000, 2_080, 2_100],
  memory: [620, 700, 760, 800],
};

const KILL_LATENCY = [0, 260, 320, 340];

const BASE_SCORE = 98;

export interface MockOptions {
  fault: FaultKind;
  target: string;
  fixes: boolean;
  emit: (event: WsEvent) => void;
  onFinished?: () => void;
}

export interface MockHandle {
  stop: () => void;
}

const REVERSE: Record<string, string[]> = (() => {
  const reverse: Record<string, string[]> = {};
  for (const edge of DEFAULT_TOPOLOGY.edges) {
    (reverse[edge.target] ??= []).push(edge.source);
  }
  return reverse;
})();

function callerDepths(target: string): Map<string, number> {
  const depth = new Map<string, number>([[target, 0]]);
  let frontier = [target];
  while (frontier.length > 0) {
    const next: string[] = [];
    for (const node of frontier) {
      for (const caller of REVERSE[node] ?? []) {
        if (!depth.has(caller)) {
          depth.set(caller, (depth.get(node) ?? 0) + 1);
          next.push(caller);
        }
      }
    }
    frontier = next;
  }
  return depth;
}

function jitter(value: number): number {
  return value * (0.94 + Math.random() * 0.12);
}

interface Snapshot {
  statuses: Record<string, ServiceStatus>;
  latencies: Record<string, number>;
  errorRate: number;
  score: number;
}

function snapshot(
  elapsed: number,
  fault: FaultKind,
  depth: Map<string, number>,
): Snapshot {
  const inFault = elapsed >= BASELINE_END && elapsed < FAULT_END;
  const inBurst =
    inFault && elapsed >= BURST_START && elapsed < BURST_END && fault !== "kill";

  const statuses: Record<string, ServiceStatus> = {};
  const latencies: Record<string, number> = {};

  for (const node of DEFAULT_TOPOLOGY.nodes) {
    const base = BASELINE_LATENCY[node.id] ?? 10;
    const distance = depth.get(node.id);

    if (!inFault || distance === undefined) {
      statuses[node.id] = "ok";
      latencies[node.id] = jitter(base);
      continue;
    }

    if (fault === "kill") {
      statuses[node.id] = "bad";
      latencies[node.id] = jitter(KILL_LATENCY[distance] ?? 340);
      continue;
    }

    const series = LATENCY_BY_DEPTH[fault];
    latencies[node.id] = jitter(
      (series[Math.min(distance, series.length - 1)] ?? base) * (inBurst ? 1.05 : 1),
    );
    statuses[node.id] = distance === 0 && inBurst ? "bad" : "warn";
  }

  const gatewayLatency = latencies.gateway ?? 0;
  const errorRate = !inFault ? 0 : fault === "kill" ? 0.5 : inBurst ? 0.17 : 0;
  const ratio = gatewayLatency / (BASELINE_LATENCY.gateway || 1);
  const latencyPenalty = inFault ? Math.min(60, Math.max(0, (ratio - 1) * 30)) : 0;
  const score = inFault
    ? clamp(BASE_SCORE - latencyPenalty - errorRate * 100, 0, 100)
    : Math.min(100, BASE_SCORE + Math.random() * 1.5);

  return { statuses, latencies, errorRate, score };
}

export function startMockExperiment(options: MockOptions): MockHandle {
  const { fault, target, fixes, emit, onFinished } = options;
  const depth = callerDepths(target);
  const startedAt = Date.now();
  const runLabel = `MOCK-${String(Date.now()).slice(-4)}`;

  let timer: number | undefined;
  let previous: Record<string, ServiceStatus> = {};
  let burstLogged = false;
  let baselineLogged = false;
  let faultLogged = false;
  let recoveryLogged = false;
  let lastFaultScore = 0;

  const log = (level: "info" | "warn" | "error" | "success", text: string) =>
    emit({ type: "log", level, text });

  log("success", `mock link established // replaying scripted run ${runLabel}`);
  log(
    "info",
    `Experiment ${runLabel} started: ${fault} on ${target} (fixes=${fixes ? "on" : "off"})`,
  );

  const stop = () => {
    if (timer !== undefined) {
      window.clearInterval(timer);
      timer = undefined;
    }
  };

  const tick = () => {
    const elapsed = Date.now() - startedAt;
    const snap = snapshot(elapsed, fault, depth);

    if (!baselineLogged) {
      baselineLogged = true;
      log("info", "Baseline for 10s: collecting normal traffic");
    }

    if (!faultLogged && elapsed >= BASELINE_END) {
      faultLogged = true;
      log("warn", `Injecting ${fault} on ${target} for 20s`);
      log("warn", `Fault active: ${fault} on ${target}`);
    }

    if (elapsed >= BURST_START && elapsed < BURST_END && !burstLogged) {
      burstLogged = true;
      log("error", `${target} stopped responding // callers degraded`);
    }

    if (!recoveryLogged && elapsed >= FAULT_END) {
      recoveryLogged = true;
      log("info", "Fault window closed; applying recovery");
      log("info", "Recovery applied; observing for 10s");
    }

    for (const node of DEFAULT_TOPOLOGY.nodes) {
      const status = snap.statuses[node.id] ?? "ok";
      const latency = Number((snap.latencies[node.id] ?? 0).toFixed(1));

      if (previous[node.id] && previous[node.id] !== status) {
        const text = `${node.id} is ${status} (${latency.toFixed(0)}ms)`;
        log(status === "ok" ? "success" : status === "warn" ? "warn" : "error", text);
      }
      previous[node.id] = status;

      emit({ type: "state", service: node.id, status, latency_ms: latency });
    }

    emit({
      type: "metrics",
      gateway_latency: Number((snap.latencies.gateway ?? 0).toFixed(1)),
      error_rate: Number(snap.errorRate.toFixed(3)),
    });

    if (elapsed >= BASELINE_END && elapsed < FAULT_END) {
      lastFaultScore = snap.score;
    }
    emit({ type: "score", value: Number(snap.score.toFixed(1)) });

    if (elapsed >= FINISH) {
      stop();
      const finalScore = Math.round(lastFaultScore || snap.score);
      log("info", `Experiment ${runLabel} completed; resilience score ${finalScore}/100`);
      emit({ type: "score", value: finalScore });
      emit({ type: "postmortem", text: buildPostmortem(runLabel, fault, target, fixes, finalScore) });
      onFinished?.();
    }
  };

  tick();
  timer = window.setInterval(tick, TICK);

  return { stop };
}

function buildPostmortem(
  runLabel: string,
  fault: FaultKind,
  target: string,
  fixes: boolean,
  score: number,
): string {
  const baseline = 66;
  const faultWindow = fault === "kill" ? 340 : fault === "memory" ? 760 : 2_080;
  const ratio = (faultWindow / baseline).toFixed(1);
  return [
    `Experiment ${runLabel}: injected ${fault} on ${target} (fixes=${fixes ? "on" : "off"}).`,
    `Baseline: gateway p50 ${baseline}ms, errors 0/10.`,
    `Fault: gateway p50 ${faultWindow}ms, errors ${fault === "kill" ? 5 : 0}/20.`,
    `Recovery: gateway p50 68ms, errors 0/10.`,
    `Gateway latency moved +${faultWindow - baseline}ms during the fault (${ratio}x baseline).`,
    `Resilience score: ${score}/100.`,
  ].join(" ");
}
