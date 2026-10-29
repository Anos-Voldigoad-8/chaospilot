import { AlertTriangle, FileWarning, Server, ShieldCheck, Zap } from "lucide-react";
import type { OverviewSummary } from "../types/api";

interface SummaryCardsProps {
  summary: OverviewSummary;
}

const cards = [
  {
    key: "services_total" as const,
    label: "Services",
    icon: Server,
    accent: "text-cyan-300",
    ring: "border-cyan-500/20",
  },
  {
    key: "services_healthy" as const,
    label: "Healthy",
    icon: ShieldCheck,
    accent: "text-emerald-300",
    ring: "border-emerald-500/20",
  },
  {
    key: "active_faults" as const,
    label: "Active faults",
    icon: Zap,
    accent: "text-amber-300",
    ring: "border-amber-500/20",
  },
  {
    key: "anomalies_recent" as const,
    label: "Anomalies",
    icon: AlertTriangle,
    accent: "text-rose-300",
    ring: "border-rose-500/20",
  },
  {
    key: "incidents_recent" as const,
    label: "Incidents",
    icon: FileWarning,
    accent: "text-violet-300",
    ring: "border-violet-500/20",
  },
];

export function SummaryCards({ summary }: SummaryCardsProps) {
  return (
    <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.key}
            className={`rounded-xl border ${card.ring} bg-ink-900/70 px-4 py-3 backdrop-blur`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-wider text-slate-500">
                {card.label}
              </span>
              <Icon className={`h-4 w-4 ${card.accent}`} aria-hidden />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-semibold tabular-nums text-white">
                {summary[card.key]}
              </span>
              {card.key === "services_total" ? (
                <span className="text-[11px] text-slate-500">
                  {summary.services_degraded} degraded
                </span>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
