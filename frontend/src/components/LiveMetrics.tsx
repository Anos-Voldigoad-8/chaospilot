import {
  AreaChart,
  Area,
  CartesianGrid,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { useChaosStore } from "../store/useChaosStore";
import { formatPercent, percentile } from "../lib/stats";
import { COLORS } from "../lib/theme";
import { Panel } from "./Panel";
import { ResilienceGauge } from "./ResilienceGauge";
import { AnimatedCounter } from "./common/AnimatedCounter";
import { Activity, AlertOctagon, TrendingUp, Cpu } from "lucide-react";

export function LiveMetrics() {
  const metrics = useChaosStore((state) => state.metrics);
  const score = useChaosStore((state) => state.score);
  const breakdown = useChaosStore((state) => state.scoreBreakdown);
  const anomaly = useChaosStore((state) => state.anomaly);
  const running = useChaosStore((state) => state.running);
  const activeExperimentId = useChaosStore((state) => state.activeExperimentId);

  const recent = metrics.slice(-60);
  const p95 = percentile(
    recent.map((sample) => sample.latency),
    0.95,
  );
  const latest = recent.at(-1);
  const errorRate = latest?.errorRate ?? 0;
  const errorColor =
    errorRate > 0.02 ? COLORS.red : errorRate > 0 ? COLORS.amber : COLORS.ultraviolet;
  const anomalyColor =
    anomaly >= 0.7 ? COLORS.red : anomaly >= 0.4 ? COLORS.amber : COLORS.ultraviolet;

  const chartData = metrics.map((sample, index) => ({
    index,
    latency: Number(sample.latency.toFixed(1)),
    error: Number((sample.errorRate * 100).toFixed(2)),
  }));

  return (
    <Panel
      title="Cluster Telemetry"
      code="1Hz SAMPLING"
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
      bodyClassName="flex flex-col gap-3 p-3.5"
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

        {/* Error Rate Card */}
        <div className="border border-[#DDE1EA] bg-[#F8F9FB] p-2.5 shadow-card backdrop-blur-sm hover:border-ultraviolet/50 transition-colors">
          <div className="flex items-center justify-between text-[7.5px] uppercase tracking-[0.16em] text-gunmetal-500 font-bold">
            <span>ERROR RATE</span>
            <AlertOctagon className="h-2.5 w-2.5" style={{ color: errorColor }} />
          </div>
          <div
            className="mt-1 font-mono text-[19px] font-black leading-none"
            style={{ color: errorColor }}
          >
            {formatPercent(errorRate)}
          </div>
          <div className="mt-1 text-[7.5px] uppercase tracking-wider text-gunmetal-500 font-semibold">
            HTTP 5XX DELTA
          </div>
        </div>

        {/* ML Anomaly Score Card */}
        <div className="border border-[#DDE1EA] bg-[#F8F9FB] p-2.5 shadow-card backdrop-blur-sm hover:border-ultraviolet/50 transition-colors">
          <div className="flex items-center justify-between text-[7.5px] uppercase tracking-[0.16em] text-gunmetal-500 font-bold">
            <span>ML ANOMALY</span>
            <Cpu className="h-2.5 w-2.5" style={{ color: anomalyColor }} />
          </div>
          <div
            className="mt-1 font-mono text-[19px] font-black leading-none"
            style={{ color: anomalyColor }}
          >
            <AnimatedCounter value={anomaly * 100} duration={400} suffix="%" />
          </div>
          <div className="mt-1 text-[7.5px] uppercase tracking-wider text-gunmetal-500 font-semibold">
            ISOLATION FOREST
          </div>
        </div>
      </div>

      {/* 3. Live Latency & Error Trace Area Chart */}
      <div className="border border-[#DDE1EA] bg-[#F8F9FB] p-2.5 shadow-card font-mono backdrop-blur-sm">
        <div className="flex items-center justify-between px-1 pb-1.5 text-[8px] uppercase tracking-wider border-b border-[#DDE1EA] mb-2">
          <span className="text-gunmetal-500 flex items-center gap-1.5 font-bold">
            <Activity className="h-3 w-3 text-ultraviolet" />
            TELEMETRY STREAM (60s)
          </span>
          <div className="flex items-center gap-3 font-semibold">
            <span className="flex items-center gap-1 text-gunmetal-900">
              <span className="h-1.5 w-1.5 rounded-full bg-ultraviolet shadow-ultravioletSm" /> LATENCY
            </span>
            <span className="flex items-center gap-1 text-signal-red">
              <span className="h-1.5 w-1.5 rounded-full bg-signal-red" /> ERROR %
            </span>
          </div>
        </div>

        <div className="relative h-[116px] w-full">
          {chartData.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center font-mono text-[9px] uppercase tracking-[0.2em] text-gunmetal-500 font-bold">
              STREAM CALIBRATING...
            </div>
          ) : null}

          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 6, right: 2, bottom: 0, left: 2 }}>
              <defs>
                <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366F1" stopOpacity={0.14} />
                  <stop offset="95%" stopColor="#6366F1" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="errorGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#EF4444" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#EF4444" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#E8EBF1" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="index" hide />
              <YAxis yAxisId="latency" hide domain={[0, "dataMax + 120"]} />
              <YAxis yAxisId="error" hide domain={[0, 100]} orientation="right" />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    return (
                      <div className="border border-[#DDE1EA] bg-[#F8F9FB]/95 backdrop-blur-md p-2 font-mono text-[9px] uppercase shadow-card">
                        <div className="text-ultraviolet font-bold">
                          LATENCY: {payload[0]?.value}ms
                        </div>
                        <div className="text-signal-red font-bold">
                          ERROR: {payload[1]?.value}%
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Area
                yAxisId="latency"
                type="monotone"
                dataKey="latency"
                stroke="#6366F1"
                strokeWidth={1.8}
                fill="url(#latencyGradient)"
                isAnimationActive={false}
              />
              <Area
                yAxisId="error"
                type="monotone"
                dataKey="error"
                stroke="#EF4444"
                strokeWidth={1.8}
                fill="url(#errorGradient)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 4. Blast Radius & Cascade Containment Status */}
      <div className="border-t border-[#DDE1EA] pt-2.5 flex flex-wrap items-center justify-between gap-2 font-mono text-[8px] uppercase tracking-wider text-gunmetal-500">
        <div className="flex items-center gap-1.5 font-bold">
          <span
            className={`px-1.5 py-0.5 border ${
              breakdown.contained
                ? "border-ultraviolet/40 bg-ultraviolet/14 text-ultraviolet"
                : "border-signal-red/30 bg-signal-redLight text-signal-red"
            }`}
          >
            {breakdown.contained ? "BLAST RADIUS CONTAINED" : "UNCONTAINED SPREAD"}
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
