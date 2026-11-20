import { GitCompareArrows, ShieldAlert, ShieldCheck, ArrowUpRight } from "lucide-react";
import { useChaosStore } from "../store/useChaosStore";
import { formatRelative } from "../lib/stats";
import { COLORS } from "../lib/theme";
import type { RunOutcome } from "../types/chaos";
import { Panel } from "./Panel";
import { AnimatedCounter } from "./common/AnimatedCounter";

function ComparisonCard({
  run,
  label,
  isResilient,
}: {
  run: RunOutcome | null;
  label: string;
  isResilient: boolean;
}) {
  const accentColor = isResilient ? COLORS.ultraviolet : COLORS.red;
  const score = run?.score ?? 0;

  return (
    <div
      className={`border p-3 flex flex-col justify-between transition-all bg-[#F8F9FB] shadow-card ${isResilient
          ? "border-ultraviolet/40 border-t-2"
          : "border-signal-red/40 border-t-2"
        }`}
    >
      <div>
        <div className="flex items-center justify-between text-[8px] font-mono uppercase tracking-[0.16em]">
          <span className="flex items-center gap-1 font-bold" style={{ color: accentColor }}>
            {isResilient ? (
              <ShieldCheck className="h-3 w-3 text-ultraviolet" />
            ) : (
              <ShieldAlert className="h-3 w-3 text-signal-red" />
            )}
            {label}
          </span>
          <span className="text-gunmetal-500 font-bold">{run ? `#${run.id}` : "NO DATA"}</span>
        </div>

        <div className="mt-2.5 flex items-baseline gap-1">
          <span
            className="font-mono text-[30px] font-black leading-none tabular-nums text-gunmetal-900"
          >
            {run ? <AnimatedCounter value={score} duration={500} /> : "--"}
          </span>
          <span className="font-mono text-[10px] text-gunmetal-500 font-bold">/100</span>
        </div>
      </div>

      <div className="mt-3.5">
        {/* Progress track */}
        <div className="h-2 w-full bg-[#DDE1EA] overflow-hidden border border-[#DDE1EA]">
          <div
            className="h-full transition-all duration-700 ease-out"
            style={{
              width: `${run ? score : 0}%`,
              backgroundColor: accentColor,
            }}
          />
        </div>

        <div className="mt-1.5 truncate font-mono text-[7.5px] uppercase tracking-wider text-gunmetal-500 font-semibold">
          {run ? `${run.fault} → ${run.target} · ${formatRelative(run.at)}` : "RUN EXPERIMENT TO COMPARE"}
        </div>
      </div>
    </div>
  );
}

export function ComparePanel() {
  const compareOff = useChaosStore((state) => state.compareOff);
  const compareOn = useChaosStore((state) => state.compareOn);

  const delta =
    compareOff !== null && compareOn !== null ? compareOn.score - compareOff.score : null;

  return (
    <Panel
      title="Resilience Differential"
      code="OFF VS ON"
      actions={
        <div className="flex items-center gap-1.5 font-mono text-[8px] uppercase tracking-wider">
          <GitCompareArrows className="h-3 w-3 text-gunmetal-500" />
          <span className="text-gunmetal-500 font-bold">DELTA:</span>
          <span
            className="font-bold px-1.5 py-0.5 border"
            style={{
              color: delta === null ? COLORS.muted : delta >= 0 ? COLORS.ultraviolet : COLORS.red,
              borderColor:
                delta === null
                  ? "#DDE1EA"
                  : delta >= 0
                    ? `${COLORS.ultraviolet}60`
                    : `${COLORS.red}60`,
              backgroundColor:
                delta === null
                  ? "#F8F9FB"
                  : delta >= 0
                    ? "rgba(99, 102, 241, 0.14)"
                    : "rgba(239, 68, 68, 0.12)",
            }}
          >
            {delta === null ? "--" : `${delta >= 0 ? "+" : ""}${delta} PTS`}
          </span>
        </div>
      }
      bodyClassName="flex flex-col gap-2.5 p-3.5 font-mono"
    >
      {/* Dual Comparative Bento Cards */}
      <div className="grid grid-cols-2 gap-2.5">
        <ComparisonCard run={compareOff} label="FRAGILE (OFF)" isResilient={false} />
        <ComparisonCard run={compareOn} label="SHIELD (ON)" isResilient={true} />
      </div>

      {/* Delta Verdict Banner */}
      <div className="border border-[#DDE1EA] bg-[#F8F9FB] p-2.5 font-mono text-[8.5px] uppercase tracking-wider leading-relaxed shadow-metal">
        {delta !== null ? (
          <div className="flex items-center gap-2">
            <ArrowUpRight className="h-4 w-4 text-ultraviolet shrink-0" />
            <span className="text-gunmetal-900 font-semibold">
              {delta >= 0
                ? `RECOVERY SHIELD IMPROVED RESILIENCE BY +${delta} POINTS WITH ACTIVE CIRCUIT BREAKERS.`
                : `RESILIENCE DECREASED BY ${Math.abs(delta)} POINTS UNDER CURRENT LOAD PROFILE.`}
            </span>
          </div>
        ) : (
          <span className="text-gunmetal-500 font-semibold">
            {compareOff === null && compareOn === null
              ? "RUN ONCE WITH FIXES OFF AND ONCE WITH FIXES ON TO MEASURE COMPARISON."
              : compareOff === null
                ? "RUN AN EXPERIMENT WITH FIXES OFF TO COMPLETE COMPARISON."
                : "RUN AN EXPERIMENT WITH FIXES ON TO MEASURE RESILIENCE GAIN."}
          </span>
        )}
      </div>
    </Panel>
  );
}
