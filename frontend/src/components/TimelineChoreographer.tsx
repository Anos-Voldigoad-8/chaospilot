import { useEffect, useState } from "react";
import { useChaosStore } from "../store/useChaosStore";
import { Play, CheckCircle2, AlertTriangle, ShieldCheck, Flame } from "lucide-react";
import { audioEngine } from "../lib/audio";

export function TimelineChoreographer() {
  const running = useChaosStore((state) => state.running);
  const selectedScenarioId = useChaosStore((state) => state.selectedScenarioId);
  const scenarios = useChaosStore((state) => state.scenarios);
  const score = useChaosStore((state) => state.score);
  const postmortem = useChaosStore((state) => state.postmortem);

  const scenario = selectedScenarioId != null
    ? scenarios.find((s) => s.id === selectedScenarioId)
    : null;

  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    let interval: number;
    if (running) {
      setElapsed(0);
      audioEngine.playFaultAlert();
      interval = window.setInterval(() => {
        setElapsed((prev) => {
          const next = prev + 1;
          if (next === 10) audioEngine.playFaultAlert();
          if (next === 30) audioEngine.playRecovery();
          return next;
        });
      }, 1000);
    } else {
      if (score > 0 || postmortem) {
        audioEngine.playRecovery();
      }
    }
    return () => clearInterval(interval);
  }, [running, score, postmortem]);

  // Total standard experiment duration = 40s (10 baseline + 20 fault + 10 recovery)
  const totalDuration = 40;
  const progressPercent = running
    ? Math.min(100, (elapsed / totalDuration) * 100)
    : score > 0
      ? 100
      : 0;

  // Determine current active phase
  let currentPhase = "Standby Ready";
  let phaseColor = "text-gunmetal-500";
  if (running) {
    if (elapsed < 10) {
      currentPhase = "Phase 1: Baseline Calibration (0-10s)";
      phaseColor = "text-gunmetal-900 font-bold";
    } else if (elapsed < 30) {
      currentPhase = `Phase 2: Injected Fault [${scenario?.fault_type?.toUpperCase() ?? "FAULT"}] (10-30s)`;
      phaseColor = "text-signal-red font-bold";
    } else {
      currentPhase = "Phase 3: Resilient Recovery (30-40s)";
      phaseColor = "text-ultraviolet font-bold";
    }
  } else if (score > 0) {
    currentPhase = `Experiment Concluded — Resilience: ${Math.round(score)}/100`;
    phaseColor = "text-ultraviolet font-bold";
  }

  return (
    <div className="border border-[#DDE1EA] bg-[#F8F9FB]/95 p-2.5 shadow-card backdrop-blur-md">
      <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[9px] uppercase tracking-[0.14em]">
        <div className="flex items-center gap-2">
          {running ? (
            <Flame className="h-3.5 w-3.5 text-signal-red animate-pulse" />
          ) : score > 0 ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-ultraviolet" />
          ) : (
            <Play className="h-3.5 w-3.5 text-gunmetal-500" />
          )}
          <span className={phaseColor}>{currentPhase}</span>
        </div>
        <div className="flex items-center gap-2 font-mono text-[10px] text-ultraviolet font-bold">
          <span>{running ? `${elapsed}s / ${totalDuration}s` : "40s Window"}</span>
        </div>
      </div>

      {/* Progress Track */}
      <div className="relative mt-2 h-2 w-full overflow-hidden border border-[#DDE1EA] bg-[#DDE1EA]">
        {/* Phase markers */}
        <div className="absolute left-[25%] top-0 h-full w-px bg-gunmetal-500 z-10" title="10s: Fault start" />
        <div className="absolute left-[75%] top-0 h-full w-px bg-gunmetal-500 z-10" title="30s: Recovery start" />

        <div
          className={`h-full transition-all duration-300 ${
            elapsed >= 10 && elapsed < 30
              ? "bg-signal-red shadow-red"
              : "bg-gradient-to-r from-ultraviolet to-ultraviolet-deep shadow-[0_0_12px_rgba(99,102,241,0.14)]"
          }`}
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Phase Legend */}
      <div className="mt-1.5 flex justify-between font-mono text-[8px] uppercase tracking-wider text-gunmetal-500">
        <span className="flex items-center gap-1 font-semibold text-gunmetal-900">
          <span className="h-1.5 w-1.5 rounded-full bg-ultraviolet" />
          0s Baseline
        </span>
        <span className="flex items-center gap-1 font-semibold text-signal-red">
          <AlertTriangle className="h-2.5 w-2.5 text-signal-red" />
          10s Fault
        </span>
        <span className="flex items-center gap-1 font-semibold text-ultraviolet">
          <ShieldCheck className="h-2.5 w-2.5 text-ultraviolet" />
          30s Recovery
        </span>
        <span className="font-semibold text-gunmetal-500">40s End</span>
      </div>
    </div>
  );
}
