import { GitCompareArrows } from "lucide-react";
import { useChaosStore } from "../store/useChaosStore";
import { formatRelative } from "../lib/stats";
import { COLORS, scoreColor } from "../lib/theme";
import type { RunOutcome } from "../types/chaos";
import { Panel } from "./Panel";

function ScoreCard({
  run,
  label,
  accent,
}: {
  run: RunOutcome | null;
  label: string;
  accent: string;
}) {
  return (
    <div className="border border-neon-cyan/10 bg-void-950/50 px-2 py-2">
      <div className="flex items-center justify-between gap-2">
        <span
          className="text-[8px] font-semibold uppercase tracking-[0.18em]"
          style={{ color: accent }}
        >
          {label}
        </span>
        <span className="text-[8px] uppercase tracking-[0.12em] text-slate-700">
          {run ? `#${run.id ?? "--"}` : "no run"}
        </span>
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <span
          className="font-mono text-[26px] font-medium leading-none tabular-nums"
          style={{ color: run ? scoreColor(run.score) : COLORS.muted }}
        >
          {run ? run.score : "--"}
        </span>
        <span className="text-[9px] uppercase tracking-[0.12em] text-slate-600">/100</span>
      </div>
      <div className="mt-2 h-1 w-full overflow-hidden bg-void-900">
        <div
          className="h-full transition-all duration-700"
          style={{
            width: `${run?.score ?? 0}%`,
            backgroundColor: run ? scoreColor(run.score) : COLORS.muted,
          }}
        />
      </div>
      <div className="mt-1.5 truncate text-[8px] uppercase tracking-[0.12em] text-slate-600">
        {run ? `${run.fault} → ${run.target} · ${formatRelative(run.at)}` : "run to populate"}
      </div>
    </div>
  );
}

export function ComparePanel() {
  const compareOff = useChaosStore((state) => state.compareOff);
  const compareOn = useChaosStore((state) => state.compareOn);

  const delta =
    compareOff !== null && compareOn !== null ? compareOn.score - compareOff.score : null;
  const missing =
    compareOff === null && compareOn === null
      ? "Run once with fixes off and once with fixes on."
      : compareOff === null
        ? "Last run with fixes off is still missing."
        : compareOn === null
          ? "Last run with fixes on is still missing."
          : null;

  return (
    <Panel
      title="Compare"
      code="fixes off vs on"
      actions={
        <span className="flex items-center gap-1.5 text-[8px] uppercase tracking-[0.16em] text-slate-600">
          <GitCompareArrows className="h-3 w-3 text-neon-cyan/40" aria-hidden />
          delta
          <span
            className="font-semibold"
            style={{ color: delta === null ? COLORS.muted : scoreColor(50 + (delta ?? 0)) }}
          >
            {delta === null ? "--" : `${delta > 0 ? "+" : ""}${delta}`}
          </span>
        </span>
      }
      bodyClassName="flex flex-col gap-2 p-3"
    >
      <div className="grid grid-cols-2 gap-2">
        <ScoreCard run={compareOff} label="fixes off" accent={COLORS.red} />
        <ScoreCard run={compareOn} label="fixes on" accent={COLORS.mint} />
      </div>
      <p
        className="text-[9px] uppercase leading-[1.5] tracking-[0.1em]"
        style={{ color: missing ? COLORS.amber : COLORS.muted }}
      >
        {missing ??
          (delta !== null && delta >= 0
            ? `Resilience improved by ${delta} points with fixes on.`
            : `Resilience dropped by ${Math.abs(delta ?? 0)} points with fixes on.`)}
      </p>
      <p className="border-t border-neon-cyan/10 pt-1.5 text-[8px] uppercase tracking-[0.12em] text-slate-700">
        100 − 15 per failed − 6 per degraded + 10 contained bonus
      </p>
    </Panel>
  );
}
