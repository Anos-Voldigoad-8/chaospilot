import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { useChaosStore } from "../store/useChaosStore";
import { formatLatency, formatPercent, percentile } from "../lib/stats";
import { COLORS, scoreColor } from "../lib/theme";
import { Panel } from "./Panel";
import { ResilienceGauge } from "./ResilienceGauge";

function Stat({
  label,
  value,
  hint,
  color,
}: {
  label: string;
  value: string;
  hint: string;
  color: string;
}) {
  return (
    <div className="border border-neon-cyan/10 bg-void-950/50 px-2 py-2">
      <div className="text-[8px] uppercase tracking-[0.18em] text-slate-600">{label}</div>
      <div className="mt-1 font-mono text-[19px] font-medium leading-none" style={{ color }}>
        {value}
      </div>
      <div className="mt-1 text-[8px] uppercase tracking-[0.12em] text-slate-600">{hint}</div>
    </div>
  );
}

export function LiveMetrics() {
  const metrics = useChaosStore((state) => state.metrics);
  const score = useChaosStore((state) => state.score);
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
    errorRate > 0.02 ? COLORS.red : errorRate > 0 ? COLORS.amber : COLORS.mint;

  const chartData = metrics.map((sample, index) => ({
    index,
    latency: Number(sample.latency.toFixed(1)),
    error: Number((sample.errorRate * 100).toFixed(2)),
  }));

  return (
    <Panel
      title="Telemetry"
      code="gateway"
      actions={
        <span className="flex items-center gap-1.5 text-[8px] uppercase tracking-[0.16em]">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              running ? "animate-pulse bg-neon-red" : "bg-slate-600"
            }`}
          />
          <span className={running ? "text-neon-red" : "text-slate-600"}>
            {running ? `rec · #${activeExperimentId ?? "--"}` : "idle"}
          </span>
        </span>
      }
      bodyClassName="flex flex-col gap-3 p-3"
    >
      <ResilienceGauge score={score} />

      <div className="grid grid-cols-2 gap-2">
        <Stat
          label="p95 latency"
          value={formatLatency(p95)}
          hint={`${recent.length} samples`}
          color={p95 !== null && p95 > 1_000 ? COLORS.amber : COLORS.cyan}
        />
        <Stat
          label="error rate"
          value={formatPercent(errorRate)}
          hint="latest tick"
          color={errorColor}
        />
      </div>

      <div className="border border-neon-cyan/10 bg-void-950/50 p-1.5">
        <div className="flex items-center justify-between px-0.5 pb-1">
          <span className="text-[8px] uppercase tracking-[0.18em] text-slate-600">
            live stream
          </span>
          <span className="flex items-center gap-2 text-[8px] uppercase tracking-[0.12em]">
            <span className="flex items-center gap-1 text-neon-cyan/60">
              <span className="h-px w-3 bg-neon-cyan" /> latency
            </span>
            <span className="flex items-center gap-1 text-neon-red/70">
              <span className="h-px w-3 bg-neon-red" /> error
            </span>
          </span>
        </div>

        <div className="relative h-[112px] w-full">
          {chartData.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center text-[9px] uppercase tracking-[0.2em] text-slate-700">
              awaiting telemetry
            </div>
          ) : null}
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 4, right: 2, bottom: 0, left: 2 }}>
              <CartesianGrid stroke="rgba(32,231,222,0.06)" strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="index" hide />
              <YAxis yAxisId="latency" hide domain={[0, "dataMax + 120"]} />
              <YAxis yAxisId="error" hide domain={[0, 100]} orientation="right" />
              <Line
                yAxisId="latency"
                type="monotone"
                dataKey="latency"
                stroke={COLORS.cyan}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                yAxisId="error"
                type="monotone"
                dataKey="error"
                stroke={COLORS.red}
                strokeWidth={1}
                strokeDasharray="3 3"
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="flex items-center justify-between border-t border-neon-cyan/10 pt-2 text-[8px] uppercase tracking-[0.14em] text-slate-600">
        <span>gateway /checkout</span>
        <span style={{ color: scoreColor(score) }}>
          resilience {Math.round(score)}
        </span>
      </div>
    </Panel>
  );
}
