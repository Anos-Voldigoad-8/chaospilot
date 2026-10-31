import { Bot, ChevronRight, Play, Radar } from "lucide-react";
import { useChaosStore } from "../store/useChaosStore";
import { formatRelative } from "../lib/stats";
import { scoreColor } from "../lib/theme";
import type { FaultKind, ExperimentSummary } from "../types/chaos";
import { Panel } from "./Panel";

const FAULTS: { id: FaultKind; label: string; hint: string }[] = [
  { id: "latency", label: "latency", hint: "inject 2s delay" },
  { id: "kill", label: "kill", hint: "stop the container" },
  { id: "memory", label: "memory", hint: "memory pressure" },
];

function ExperimentRow({ run }: { run: ExperimentSummary }) {
  const loadExperiment = useChaosStore((state) => state.loadExperiment);
  const color = scoreColor(run.score ?? 0);

  return (
    <button
      type="button"
      onClick={() => void loadExperiment(run.id)}
      className="group w-full border border-transparent px-2 py-1.5 text-left transition hover:border-neon-cyan/20 hover:bg-neon-cyan/[0.04]"
      title="Load this postmortem"
    >
      <div className="flex items-baseline gap-1.5">
        <span className="text-[9px] text-slate-600">#{run.id}</span>
        <span className="truncate font-display text-[12px] uppercase tracking-[0.1em] text-slate-300 group-hover:text-neon-ice">
          {run.fault}
          <span className="mx-1 text-neon-cyan/40">→</span>
          {run.target}
        </span>
        <span
          className="ml-auto shrink-0 text-[11px] font-semibold tabular-nums"
          style={{ color }}
        >
          {run.score ?? "--"}
        </span>
      </div>
      <div className="mt-0.5 flex items-center gap-1.5 text-[8px] uppercase tracking-[0.14em] text-slate-600">
        <span
          className="inline-block h-1 w-1 rounded-full"
          style={{ backgroundColor: run.status === "failed" ? "#ff3d55" : color }}
        />
        <span>{run.status}</span>
        <span className="text-slate-700">/</span>
        <span>{formatRelative(run.started)}</span>
        {run.fixes ? <span className="ml-auto text-neon-cyan/40">resilient</span> : null}
      </div>
    </button>
  );
}

export function ControlPanel() {
  const fault = useChaosStore((state) => state.fault);
  const target = useChaosStore((state) => state.target);
  const setFault = useChaosStore((state) => state.setFault);
  const setTarget = useChaosStore((state) => state.setTarget);
  const topology = useChaosStore((state) => state.topology);
  const experiments = useChaosStore((state) => state.experiments);
  const running = useChaosStore((state) => state.running);
  const planning = useChaosStore((state) => state.planning);
  const agentPlan = useChaosStore((state) => state.agentPlan);
  const lastError = useChaosStore((state) => state.lastError);
  const runExperiment = useChaosStore((state) => state.runExperiment);
  const runAgentExperiment = useChaosStore((state) => state.runAgentExperiment);
  const busy = running || planning;

  const hint = FAULTS.find((item) => item.id === fault)?.hint ?? "";

  return (
    <Panel
      title="Control"
      code="inject"
      actions={
        <span className="text-[8px] uppercase tracking-[0.2em] text-slate-600">
          {experiments.length} runs
        </span>
      }
      bodyClassName="flex flex-col gap-4 p-3"
    >
      <div>
        <label className="hud-label mb-1.5 block" htmlFor="fault-select">
          fault type
        </label>
        <select
          id="fault-select"
          className="hud-select"
          value={fault}
          disabled={busy}
          onChange={(event) => setFault(event.target.value as FaultKind)}
        >
          {FAULTS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
        <p className="mt-1 text-[9px] uppercase tracking-[0.12em] text-slate-600">{hint}</p>
      </div>

      <div>
        <label className="hud-label mb-1.5 block" htmlFor="target-select">
          target service
        </label>
        <select
          id="target-select"
          className="hud-select"
          value={target}
          disabled={busy}
          onChange={(event) => setTarget(event.target.value)}
        >
          {topology.nodes.map((node) => (
            <option key={node.id} value={node.id}>
              {node.label} :{node.port}
            </option>
          ))}
        </select>
        <p className="mt-1 text-[9px] uppercase tracking-[0.12em] text-slate-600">
          {topology.nodes.find((node) => node.id === target)?.role ?? "service"}
        </p>
      </div>

      <button
        type="button"
        onClick={() => void runExperiment()}
        disabled={busy}
        className={`group relative w-full overflow-hidden border px-3 py-3 text-center transition ${
          running
            ? "cursor-wait border-neon-amber/50 bg-neon-amber/10 text-neon-amber"
            : busy
              ? "cursor-wait border-slate-700 bg-void-900/60 text-slate-500"
              : "border-neon-cyan/50 bg-neon-cyan/[0.07] text-neon-cyan hover:bg-neon-cyan/[0.14] hover:shadow-cyan"
        }`}
      >
        <span className="hud-corner hud-corner-tl !border-neon-cyan/80" aria-hidden />
        <span className="hud-corner hud-corner-tr !border-neon-cyan/80" aria-hidden />
        <span className="hud-corner hud-corner-bl !border-neon-cyan/80" aria-hidden />
        <span className="hud-corner hud-corner-br !border-neon-cyan/80" aria-hidden />

        <span className="flex items-center justify-center gap-2 font-display text-[17px] font-bold uppercase tracking-[0.32em]">
          {running ? (
            <Radar className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Play className="h-4 w-4" aria-hidden />
          )}
          {running ? "running" : "run"}
        </span>
        <span className="mt-0.5 block text-[8px] uppercase tracking-[0.28em] opacity-60">
          {running ? "experiment in progress" : "experiment"}
        </span>
      </button>

      <button
        type="button"
        onClick={() => void runAgentExperiment()}
        disabled={busy}
        className={`flex w-full items-center justify-center gap-2 border px-3 py-2 text-center transition ${
          planning
            ? "cursor-wait border-neon-mint/50 bg-neon-mint/10 text-neon-mint"
            : busy
              ? "cursor-wait border-slate-700 bg-void-900/60 text-slate-500"
              : "border-neon-mint/40 bg-neon-mint/[0.05] text-neon-mint hover:bg-neon-mint/[0.12]"
        }`}
        title="Let the agent pick the next experiment"
      >
        {planning ? (
          <Radar className="h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : (
          <Bot className="h-3.5 w-3.5" aria-hidden />
        )}
        <span className="font-display text-[11px] font-semibold uppercase tracking-[0.2em]">
          {planning ? "planning" : "agent mode"}
        </span>
        <span className="text-[8px] uppercase tracking-[0.16em] opacity-60">
          {planning ? "asking the planner" : "auto-run"}
        </span>
      </button>

      {agentPlan ? (
        <div className="border border-neon-mint/20 bg-neon-mint/[0.04] px-2 py-2">
          <div className="flex items-center justify-between gap-2 text-[8px] uppercase tracking-[0.16em]">
            <span className="text-neon-mint/80">agent plan</span>
            <span className="text-slate-600">{agentPlan.source}</span>
          </div>
          <div className="mt-1 font-mono text-[11px] text-slate-300">
            {agentPlan.fault} <span className="text-neon-cyan/40">→</span> {agentPlan.target}
          </div>
          <p className="mt-1 text-[9.5px] leading-[1.5] text-slate-500">
            {agentPlan.hypothesis}
          </p>
        </div>
      ) : null}

      {lastError ? (
        <p className="border border-neon-red/25 bg-neon-red/[0.05] px-2 py-1.5 text-[9px] uppercase tracking-[0.1em] text-neon-red/80">
          {lastError}
        </p>
      ) : null}

      <div className="grid grid-cols-3 gap-1 border-y border-neon-cyan/10 py-2 text-center">
        {[
          ["10s", "baseline"],
          ["20s", "fault"],
          ["10s", "recovery"],
        ].map(([value, label]) => (
          <div key={label}>
            <div className="hud-value text-[12px]">{value}</div>
            <div className="text-[8px] uppercase tracking-[0.16em] text-slate-600">{label}</div>
          </div>
        ))}
      </div>

      <div className="flex min-h-0 flex-col">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="hud-label">run history</span>
          <ChevronRight className="h-3 w-3 text-neon-cyan/30" aria-hidden />
        </div>
        <div className="max-h-[248px] min-h-[96px] overflow-y-auto border border-neon-cyan/10 bg-void-950/50">
          {experiments.length === 0 ? (
            <p className="px-2 py-6 text-center text-[10px] uppercase tracking-[0.16em] text-slate-600">
              no runs recorded
            </p>
          ) : (
            <div className="divide-y divide-neon-cyan/[0.06]">
              {experiments.map((run) => (
                <ExperimentRow key={run.id} run={run} />
              ))}
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
