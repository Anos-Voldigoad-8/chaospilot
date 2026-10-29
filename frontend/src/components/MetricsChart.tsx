import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MetricPoint, Service } from "../types/api";
import { formatNumber, formatPercent } from "../lib/format";

type MetricKey = "latency_ms" | "error_rate" | "cpu_percent";

const METRICS: { key: MetricKey; label: string; color: string }[] = [
  { key: "latency_ms", label: "Latency", color: "#22d3ee" },
  { key: "error_rate", label: "Errors", color: "#fb7185" },
  { key: "cpu_percent", label: "CPU", color: "#a78bfa" },
];

interface MetricsChartProps {
  services: Service[];
  selectedService: string;
  onSelect: (serviceId: string) => void;
  points: MetricPoint[];
  loading: boolean;
  error: string | null;
}

export function MetricsChart({
  services,
  selectedService,
  onSelect,
  points,
  loading,
  error,
}: MetricsChartProps) {
  const [metric, setMetric] = useState<MetricKey>("latency_ms");
  const config = METRICS.find((item) => item.key === metric) ?? METRICS[0];

  const data = useMemo(
    () =>
      points.map((point) => ({
        time: new Date(point.timestamp * 1000).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        value: point[metric],
      })),
    [points, metric],
  );

  const formatValue = (value: number) =>
    metric === "error_rate" ? formatPercent(value) : formatNumber(value, 1);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {METRICS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setMetric(item.key)}
              className={`rounded-md border px-2.5 py-1 text-[11px] transition ${
                item.key === metric
                  ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
                  : "border-white/5 bg-white/[0.02] text-slate-500 hover:text-slate-300"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <select
          value={selectedService}
          onChange={(event) => onSelect(event.target.value)}
          className="field w-auto min-w-[150px]"
          aria-label="Select service"
        >
          {services.map((service) => (
            <option key={service.id} value={service.id}>
              {service.name}
            </option>
          ))}
        </select>
      </div>

      {error ? <p className="mb-3 text-xs text-rose-300">{error}</p> : null}
      {loading && points.length === 0 ? (
        <div className="grid h-[260px] place-items-center text-xs text-slate-500">
          Loading telemetry…
        </div>
      ) : (
        <div className="h-[260px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
              <defs>
                <linearGradient id="metric-gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={config.color} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={config.color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.08)" />
              <XAxis
                dataKey="time"
                tick={{ fill: "#64748b", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                minTickGap={40}
              />
              <YAxis
                tick={{ fill: "#64748b", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value: number) => formatValue(value)}
                width={60}
              />
              <Tooltip
                contentStyle={{
                  background: "#0a1020",
                  border: "1px solid rgba(148, 163, 184, 0.15)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#94a3b8" }}
                formatter={(value) => [formatValue(Number(value)), config.label]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={config.color}
                strokeWidth={2}
                fill="url(#metric-gradient)"
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="mt-2 text-[11px] text-slate-600">
        Last {points.length} samples · {config.label.toLowerCase()} for {selectedService}
      </p>
    </div>
  );
}
