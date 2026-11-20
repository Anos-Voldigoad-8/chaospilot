import { useChaosStore } from "../store/useChaosStore";
import { scoreColor } from "../lib/theme";
import { Panel } from "./Panel";
import { FileText, ShieldCheck, CheckCircle2, ArrowRight } from "lucide-react";
import { audioEngine } from "../lib/audio";

export function PostmortemPanel() {
  const postmortem = useChaosStore((state) => state.postmortem);
  const postmortemSource = useChaosStore((state) => state.postmortemSource);
  const score = useChaosStore((state) => state.score);
  const running = useChaosStore((state) => state.running);
  const applyFixes = useChaosStore((state) => state.applyFixes);
  const setApplyFixes = useChaosStore((state) => state.setApplyFixes);
  const runExperiment = useChaosStore((state) => state.runExperiment);
  const selectedScenarioId = useChaosStore((state) => state.selectedScenarioId);
  const output = postmortem;
  const typing = running && !postmortem;

  const retestWithFixes = () => {
    audioEngine.playClick();
    setApplyFixes(true);
    if (selectedScenarioId != null) {
      void runExperiment({ scenario_id: selectedScenarioId, fixes: true });
    }
  };

  return (
    <Panel
      title="Incident Postmortem & RCA"
      code="GROUNDED EVIDENCE"
      actions={
        <div className="flex items-center gap-2 font-mono text-[8px] uppercase tracking-wider font-bold">
          <span
            className={`h-2 w-2 rounded-full ${
              typing ? "animate-ping bg-signal-red" : postmortem ? "bg-ultraviolet shadow-ultravioletSm" : "bg-[#DDE1EA]"
            }`}
          />
          <span className={typing ? "text-signal-red font-bold" : postmortem ? "text-ultraviolet font-bold" : "text-gunmetal-500"}>
            {typing ? "ANALYZING..." : postmortem ? "VERIFIED RCA" : "STANDBY"}
          </span>
        </div>
      }
      bodyClassName="p-0 overflow-hidden flex flex-col font-mono"
    >
      <div className="relative h-[240px] overflow-y-auto bg-[#F8F9FB]/60 p-3.5 font-mono">
        {postmortem ? (
          <div className="flex flex-col gap-2.5">
            {/* Header quote banner */}
            <div className="border border-[#DDE1EA] bg-[#F8F9FB] p-2.5 flex items-center justify-between shadow-card">
              <span className="flex items-center gap-1.5 text-gunmetal-900 text-[9.5px] uppercase font-bold tracking-wider">
                <FileText className="h-3.5 w-3.5 text-ultraviolet" />
                POSTMORTEM ANALYSIS REPORT
              </span>
              <span className="text-[8px] font-mono text-gunmetal-500 font-bold uppercase">
                {postmortemSource === "llm" ? "LLM INFERENCE" : "DETERMINISTIC TEMPLATE"}
              </span>
            </div>

            {/* Main Typewriter Postmortem Content */}
            <div className="whitespace-pre-wrap font-mono text-[11px] leading-[1.8] text-gunmetal-900 border border-[#DDE1EA] bg-[#F8F9FB] p-3 shadow-card">
              {output}
              <span className="ml-0.5 inline-block h-3.5 w-[7px] animate-blink bg-ultraviolet align-middle shadow-ultravioletSm" />
            </div>

            {/* Evidence Tags & Attribution */}
            {!typing && (
              <div className="mt-1 pt-2 border-t border-[#DDE1EA] flex flex-wrap items-center gap-1.5">
                <span className="inline-flex items-center gap-1 border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[8px] uppercase tracking-wider text-emerald-700 font-bold">
                  <CheckCircle2 className="h-2.5 w-2.5" />
                  GROUNDED EVIDENCE
                </span>
                <span
                  className="inline-flex items-center gap-1 border px-2 py-0.5 text-[8px] uppercase tracking-wider font-bold"
                  style={{
                    color: scoreColor(score),
                    borderColor: scoreColor(score),
                    backgroundColor: score >= 80 ? "rgba(99, 102, 241, 0.14)" : score >= 50 ? "rgba(245, 158, 11, 0.12)" : "rgba(239, 68, 68, 0.12)",
                  }}
                >
                  RESILIENCE {Math.round(score)}/100
                </span>
                <span className="border border-[#DDE1EA] bg-[#F8F9FB] px-2 py-0.5 text-[8px] uppercase tracking-wider text-gunmetal-500 font-semibold shadow-paper">
                  NO SECRETS IN BROWSER
                </span>

                {/* Recommendation re-test button */}
                {!applyFixes && (
                  <button
                    type="button"
                    onClick={retestWithFixes}
                    className="ml-auto inline-flex items-center gap-1 border border-ultraviolet bg-gradient-to-r from-ultraviolet to-ultraviolet-deep px-2.5 py-1 text-[8.5px] uppercase tracking-wider text-white font-bold hover:brightness-110 transition shadow-[0_0_24px_rgba(99,102,241,0.14)] active:scale-95"
                  >
                    <span>RE-TEST WITH FIXES</span>
                    <ArrowRight className="h-2.5 w-2.5" />
                  </button>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-gunmetal-500">
            <ShieldCheck className="h-7 w-7 text-gunmetal-400" />
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] font-bold text-gunmetal-500">
              {running ? "COLLECTING TELEMETRY EVIDENCE..." : "AWAITING EXPERIMENT RUN"}
            </span>
            <span className="font-mono text-[8.5px] uppercase tracking-[0.12em] text-gunmetal-500 max-w-xs">
              {running
                ? "THE AGENT COLLECTS LATENCY DELTAS, ANOMALIES, AND CASCADE FAILURES"
                : "TRIGGER A FAULT TO GENERATE A REAL-TIME GROUNDED AI POSTMORTEM"}
            </span>
          </div>
        )}
      </div>
    </Panel>
  );
}
