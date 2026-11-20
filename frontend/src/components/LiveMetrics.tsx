import { useChaosStore } from "../store/useChaosStore";
import { formatPercent, percentile } from "../lib/stats";
import { COLORS } from "../lib/theme";
import { Panel } from "./Panel";
import { ResilienceGauge } from "./ResilienceGauge";
import { AnimatedCounter } from "./common/AnimatedCounter";
import { AlertOctagon, TrendingUp, Cpu, ShieldCheck, ShieldAlert } from "lucide-react";

export function LiveMetrics() {
  const metrics = useChaosStore((state) => state.metrics);
  const score = useChaosStore((state) => state.score);
  const breakdown = useChaosStore((state) => state.scoreBreakdown);
  const anomaly = useChaosStore((state) => state.anomaly);
  const running = useChaosStore((state) => state.running);
  const activeExperimentId = useChaosStore((state) => state.activeExperimentId);
  const services = useChaosStore((state) => state.services);

  const recent = metrics.slice(-60);
  const p95 = percentile(
    recent.map((sample) => sample.latency),
    0.95,
  );
  const latest = recent.at(-1);
  const errorRate = latest?.errorRate ?? 0;

  // STRICT RULE: Error & Anomaly signals are RED (#EF4444), NOT yellow
  const errorColor = errorRate > 0 ? COLORS.red : COLORS.ultraviolet;
  const anomalyColor = anomaly >= 0.35 ? COLORS.red : COLORS.ultraviolet;

  const failedCount = breakdown.failed.length;
  const degradedCount = breakdown.degraded.length;

  return (
    <Panel
      title="Cluster Telemetry"
      code="RESILIENCE RADAR"
      actions={
        <div className="flex items-center gap-2 font-mono text-[8px] uppercase tracking-[0.16em]">
          <span
            className={`h-2 w-2 rounded-full ${
              running ? "animate-ping bg-signal-red" : "bg-ultraviolet"
            }`}
          />
          <span className={running ? "text-signal-red font-bold" : "text-ultraviolet font-bold"}>
            {running ? `RECORDING · RUN #${activeExperimentId ?? "--"}` : "STEADY MONITOR"}
          </span>
        </div>
      }
      bodyClassName="flex flex-col justify-between gap-3 p-3.5"
    >
      {/* 1. Radar Resilience Gauge */}
      <ResilienceGauge score={score} />

      {/* 2. Key Telemetry Bento Deck */}
      <div className="grid grid-cols-3 gap-2 font-mono">
        {/* P95 Latency Card */}
        <div className="border border-[#DDE1EA] bg-[#F8F9FB] p-2.5 shadow-card backdrop-blur-sm hover:border-ultraviolet/50 transition-colors">
          <div className="flex items-center justify-between text-[7.5px] uppercase tracking-[0.16em] text-gunmetal-500 font-bold">
            <span>P95 LATENCY</span>
            <TrendingUp className="h-2.5 w-2.5 text-ultraviolet" />
          </div>
          <div className="mt-1 font-mono text-[19px] font-black leading-none text-gunmetal-900">
            <AnimatedCounter value={p95 ?? 0} duration={300} suffix="ms" />
          </div>
          <div className="mt-1 text-[7.5px] uppercase tracking-wider text-gunmetal-500 font-semibold">
            {recent.length} SAMPLES
          </div>
        </div>

        {/* Error Rate Card - Signal Red on any error */}
        <div className={`border p-2.5 shadow-card backdrop-blur-sm transition-colors ${
          errorRate > 0 ? "border-signal-red/40 bg-signal-redLight" : "border-[#DDE1EA] bg-[#F8F9FB]"
        }`}>
          <div className="flex items-center justify-between text-[7.5px] uppercase tracking-[0.16em] font-bold" style={{ color: errorColor }}>
            <span>ERROR RATE</span>
            <AlertOctagon className="h-2.5 w-2.5" />
          </div>
          <div
            className="mt-1 font-mono text-[19px] font-black leading-none"
            style={{ color: errorColor }}
          >
            {formatPercent(errorRate)}
          </div>
          <div className="mt-1 text-[7.5px] uppercase tracking-wider font-semibold text-gunmetal-500">
            HTTP 5XX DELTA
          </div>
        </div>

        {/* ML Anomaly Score Card - Signal Red on anomaly, NOT yellow */}
        <div className={`border p-2.5 shadow-card backdrop-blur-sm transition-colors ${
          anomaly >= 0.35 ? "border-signal-red/40 bg-signal-redLight" : "border-[#DDE1EA] bg-[#F8F9FB]"
        }`}>
          <div className="flex items-center justify-between text-[7.5px] uppercase tracking-[0.16em] font-bold" style={{ color: anomalyColor }}>
            <span>ML ANOMALY</span>
            <Cpu className="h-2.5 w-2.5" />
          </div>
          <div
            className="mt-1 font-mono text-[19px] font-black leading-none"
            style={{ color: anomalyColor }}
          >
            <AnimatedCounter value={anomaly * 100} duration={400} suffix="%" />
          </div>
          <div className="mt-1 text-[7.5px] uppercase tracking-wider font-semibold text-gunmetal-500">
            ISOLATION FOREST
          </div>
        </div>
      </div>

      {/* 3. Real-Time Service Status Matrix */}
      <div className="border border-[#DDE1EA] bg-[#F8F9FB] p-2.5 shadow-card font-mono">
        <div className="flex items-center justify-between pb-1.5 border-b border-[#DDE1EA] text-[8px] uppercase tracking-wider text-gunmetal-500 font-bold">
          <span>ACTIVE SERVICES HEALTH</span>
          <span className="text-gunmetal-900">6 NODES MONITORED</span>
        </div>
        <div className="grid grid-cols-3 gap-1.5 pt-2">
          {Object.entries(services).map(([name, rt]) => {
            const isError = rt.status === "bad" || rt.status === "warn";
            return (
              <div
                key={name}
                className={`flex items-center justify-between px-2 py-1 border text-[8px] uppercase tracking-wider font-mono ${
                  isError
                    ? "border-signal-red bg-signal-red text-white font-black"
                    : "border-[#DDE1EA] bg-white text-gunmetal-900 font-semibold"
                }`}
              >
                <span>{name}</span>
                <span className={`h-1.5 w-1.5 rounded-full ${isError ? "bg-white animate-pulse" : "bg-signal-green"}`} />
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. Resilience Score Formulation Breakdown */}
      <div className="border border-[#DDE1EA] bg-[#F8F9FB] p-2.5 shadow-card font-mono text-[8px] uppercase tracking-wider text-gunmetal-500">
        <div className="flex items-center justify-between pb-1 border-b border-[#DDE1EA] font-bold text-gunmetal-700">
          <span>RESILIENCE BREAKDOWN</span>
          <span>100 PT BASE</span>
        </div>
        <div className="mt-1.5 flex flex-col gap-1 text-[8.5px]">
          <div className="flex items-center justify-between">
            <span>FAILED PENALTY (-15/NODE):</span>
            <span className={failedCount > 0 ? "font-bold text-signal-red" : "text-gunmetal-700 font-semibold"}>
              {failedCount > 0 ? `-${failedCount * 15} PTS` : "0 PTS"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span>DEGRADED PENALTY (-6/NODE):</span>
            <span className={degradedCount > 0 ? "font-bold text-signal-red" : "text-gunmetal-700 font-semibold"}>
              {degradedCount > 0 ? `-${degradedCount * 6} PTS` : "0 PTS"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span>CONTAINMENT SHIELD BONUS:</span>
            <span className={breakdown.bonus > 0 ? "font-bold text-signal-green" : "text-gunmetal-700 font-semibold"}>
              {breakdown.bonus > 0 ? `+${breakdown.bonus} PTS` : "0 PTS"}
            </span>
          </div>
        </div>
      </div>

      {/* 5. Blast Radius & Cascade Containment Status */}
      <div className="border-t border-[#DDE1EA] pt-2.5 flex flex-wrap items-center justify-between gap-2 font-mono text-[8px] uppercase tracking-wider text-gunmetal-500">
        <div className="flex items-center gap-1.5 font-bold">
          <span
            className={`flex items-center gap-1 px-1.5 py-0.5 border ${
              breakdown.contained
                ? "border-ultraviolet/40 bg-ultraviolet/14 text-ultraviolet"
                : "border-signal-red/30 bg-signal-redLight text-signal-red"
            }`}
          >
            {breakdown.contained ? (
              <ShieldCheck className="h-3 w-3 text-ultraviolet" />
            ) : (
              <ShieldAlert className="h-3 w-3 text-signal-red" />
            )}
            <span>{breakdown.contained ? "BLAST RADIUS CONTAINED" : "UNCONTAINED SPREAD"}</span>
          </span>
          <span className="text-gunmetal-700">
            {breakdown.failed.length > 0
              ? `FAILED: ${breakdown.failed.join(", ")}`
              : "ZERO CRITICAL FAILS"}
          </span>
        </div>

        <span className="font-bold text-gunmetal-900">
          HEALTH: {Math.round(score)}%
        </span>
      </div>
    </Panel>
  );
}
