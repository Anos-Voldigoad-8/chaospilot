import { useTypewriter } from "../hooks/useAnimation";
import { useChaosStore } from "../store/useChaosStore";
import { scoreColor } from "../lib/theme";
import { Panel } from "./Panel";

export function PostmortemPanel() {
  const postmortem = useChaosStore((state) => state.postmortem);
  const postmortemSource = useChaosStore((state) => state.postmortemSource);
  const score = useChaosStore((state) => state.score);
  const running = useChaosStore((state) => state.running);
  const { output, typing } = useTypewriter(postmortem, 8);

  return (
    <Panel
      title="Postmortem"
      code="agent report"
      actions={
        <span className="flex items-center gap-1.5 text-[8px] uppercase tracking-[0.16em]">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              typing ? "animate-pulse bg-neon-cyan" : "bg-slate-700"
            }`}
          />
          <span className={typing ? "text-neon-cyan/70" : "text-slate-600"}>
            {typing ? "typing" : postmortem ? "complete" : "standby"}
          </span>
        </span>
      }
      bodyClassName="p-0"
    >
      <div className="relative h-[228px] overflow-y-auto bg-void-950/60 px-3 py-2.5">
        {postmortem ? (
          <>
            <p className="whitespace-pre-wrap text-[11.5px] leading-[1.75] text-slate-300">
              {output}
              <span className="ml-0.5 inline-block h-3 w-[6px] animate-blink bg-neon-cyan align-middle" />
            </p>
            {!typing ? (
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-neon-cyan/10 pt-2">
                <span className="hud-chip border-neon-cyan/20 text-neon-cyan/60">
                  grounded on telemetry
                </span>
                {postmortemSource ? (
                  <span className="hud-chip border-neon-cyan/20 text-slate-500">
                    source {postmortemSource}
                  </span>
                ) : null}
                <span
                  className="hud-chip border-neon-cyan/20"
                  style={{ color: scoreColor(score) }}
                >
                  score {Math.round(score)}/100
                </span>
                <span className="hud-chip border-slate-700 text-slate-500">
                  no secrets in browser
                </span>
              </div>
            ) : null}
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <span className="text-[10px] uppercase tracking-[0.24em] text-slate-600">
              {running ? "collecting evidence" : "no report yet"}
            </span>
            <span className="text-[9px] uppercase tracking-[0.14em] text-slate-700">
              {running
                ? "the agent is watching the fault window"
                : "run an experiment to generate a postmortem"}
            </span>
          </div>
        )}
      </div>
    </Panel>
  );
}
