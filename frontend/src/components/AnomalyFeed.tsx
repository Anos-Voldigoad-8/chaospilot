import { Activity, Cpu, Gauge, Radar } from "lucide-react";
import type { Anomaly } from "../types/api";
import { formatNumber, formatRelative, metricLabels, severityClasses } from "../lib/format";

interface AnomalyFeedProps {
  anomalies: Anomaly[];
}

const metricIcons: Record<string, typeof Gauge> = {
  latency_ms: Gauge,
  error_rate: Radar,
  cpu_percent: Cpu,
  memory_mb: Activity,
  request_rate: Activity,
};

export function AnomalyFeed({ anomalies }: AnomalyFeedProps) {
  if (anomalies.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-white/10 px-4 py-10 text-center">
        <Radar className="mx-auto h-6 w-6 text-slate-600" aria-hidden />
        <p className="mt-2 text-sm text-slate-400">No anomalies detected yet</p>
        <p className="mt-1 text-xs text-slate-600">
          Telemetry is being scored against the learned baseline.
        </p>
      </div>
    );
  }

  return (
    <ul className="space-y-2.5">
      {anomalies.map((anomaly) => {
        const Icon = metricIcons[anomaly.metric] ?? Activity;
        const severity = severityClasses[anomaly.severity] ?? severityClasses.low;
        return (
          <li
            key={anomaly.id}
            className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2.5"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2">
                <span className="mt-0.5 grid h-7 w-7 place-items-center rounded-md border border-white/5 bg-ink-800 text-slate-400">
                  <Icon className="h-3.5 w-3.5" aria-hidden />
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-slate-200">{anomaly.service_id}</span>
                    <span className={`rounded border px-1.5 py-0.5 text-[10px] uppercase ${severity}`}>
                      {anomaly.severity}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    {metricLabels[anomaly.metric] ?? anomaly.metric} ·{" "}
                    {formatNumber(anomaly.value, 2)} · score {formatNumber(anomaly.score, 2)}
                  </p>
                </div>
              </div>
              <span className="whitespace-nowrap text-[10px] text-slate-600">
                {formatRelative(anomaly.detected_at)}
              </span>
            </div>
            {anomaly.details.explanation ? (
              <p className="mt-1.5 border-l border-slate-700 pl-2 text-[11px] text-slate-500">
                {anomaly.details.explanation}
              </p>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
