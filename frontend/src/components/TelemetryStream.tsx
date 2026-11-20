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
import { Panel } from "./Panel";
import { Activity, Clock } from "lucide-react";

export function TelemetryStream() {
  const metrics = useChaosStore((state) => state.metrics);
  const running = useChaosStore((state) => state.running);
  const activeExperimentId = useChaosStore((state) => state.activeExperimentId);

  const chartData = metrics.map((sample, index) => ({
    index,
    latency: Number(sample.latency.toFixed(1)),
    error: Number((sample.errorRate * 100).toFixed(2)),
  }));

  const latest = metrics.at(-1);
  const currentLatency = latest ? `${latest.latency.toFixed(1)}ms` : "--";
  const currentError = latest ? `${(latest.errorRate * 100).toFixed(1)}%` : "0.0%";

  return (
    <Panel
      title="Telemetry Stream"
      code="60S LIVE TRACE"
      actions={
        <div className="flex items-center gap-3 font-mono text-[8px] uppercase tracking-[0.16em]">
          <div className="flex items-center gap-1.5 text-gunmetal-700 font-bold">
            <span className="h-1.5 w-1.5 rounded-full bg-ultraviolet shadow-ultravioletSm" />
            <span>LATENCY: {currentLatency}</span>
          </div>
          <div className={`flex items-center gap-1.5 font-bold ${latest && latest.errorRate > 0 ? "text-signal-red animate-pulse" : "text-signal-red"}`}>
            <span className="h-1.5 w-1.5 rounded-full bg-signal-red" />
            <span>ERROR: {currentError}</span>
          </div>
          <div className="hidden sm:flex items-center gap-1 text-[#5B6272] border-l border-[#DDE1EA] pl-2.5">
            <Clock className="h-2.5 w-2.5 text-ultraviolet" />
            <span>{running ? `RUN #${activeExperimentId ?? "--"}` : "1HZ TICK"}</span>
          </div>
        </div>
      }
      bodyClassName="p-2.5 flex flex-col justify-between bg-[#F8F9FB]"
    >
      <div className="relative h-[130px] sm:h-[145px] w-full">
        {chartData.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center font-mono text-[9px] uppercase tracking-[0.2em] text-[#5B6272] font-bold">
            STREAM CALIBRATING...
          </div>
        ) : null}

        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 6, bottom: 0, left: 6 }}>
            <defs>
              <linearGradient id="streamLatencyGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366F1" stopOpacity={0.18} />
                <stop offset="95%" stopColor="#6366F1" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="streamErrorGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#EF4444" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#EF4444" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#E8EBF1" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="index" hide />
            <YAxis yAxisId="latency" hide domain={[0, "dataMax + 120"]} />
            <YAxis
              yAxisId="error"
              hide
              domain={[0, (dataMax: number) => Math.max(5, Math.ceil(dataMax * 1.5))]}
              orientation="right"
            />
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
              strokeWidth={2}
              fill="url(#streamLatencyGradient)"
              isAnimationActive={false}
            />
            <Area
              yAxisId="error"
              type="monotone"
              dataKey="error"
              stroke="#EF4444"
              strokeWidth={2}
              fill="url(#streamErrorGradient)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-1 flex items-center justify-between border-t border-[#DDE1EA] pt-1.5 px-1 font-mono text-[7.5px] uppercase tracking-wider text-[#5B6272]">
        <span className="flex items-center gap-1 font-semibold text-gunmetal-700">
          <Activity className="h-2.5 w-2.5 text-ultraviolet" />
          <span>CONTINUOUS INGESTION (LAST 60 TICKS)</span>
        </span>
        <span className="font-bold text-gunmetal-900">
          RESOLUTION: 1000MS INTERVAL
        </span>
      </div>
    </Panel>
  );
}
