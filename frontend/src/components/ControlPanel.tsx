import { ChevronRight, Play, Radar, RefreshCw } from "lucide-react";
import { useChaosStore } from "../store/useChaosStore";
import { formatRelative } from "../lib/stats";
import { scoreColor } from "../lib/theme";
import type { ExperimentSummary, Scenario } from "../types/chaos";
import { Panel } from "./Panel";

function DataSourceBadge({ source }: { source: string }) {
  const label = source === "live" ? "LIVE" : source === "cached" ? "CACHED" : "SEED";
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] ${
        source === "live"
          ? "border-neon-mint/30 bg-neon-mint/[0.08] text-neon-mint"
          : source === "cached"
            ? "border-neon-amber/30 bg-neon-amber/[0.08] text-neon-amber"
            : "border-slate-600/30 bg-slate-700/[0.4] text-slate-400"
      }`}
    >
      {label}
    </span>
  );
}

function ScenarioRow({ scenario }: { scenario: Scenario }) {
  const selectScenario = useChaosStore((state) => state.selectScenario);
  const selected = useChaosStore((state) => state.selectedScenarioId);
  const isSelected = selected === scenario.id;

  return (
    <button
      type="button"
      onClick={() => void selectScenario(scenario.id)}
      className={`group w-full border px-2 py-2 text-left transition rounded ${
        isSelected
          ? "border-neon-cyan/50 bg-neon-cyan/[0.06]"
          : "border-transparent hover:border-neon-cyan/10 hover:bg-slate-800/40"
      }`}
      title="Select this scenario to run"
    >
      <div className="flex items-baseline gap-1.5">
        <span className="text-[9px] text-slate-600">#{scenario.id}</span>
        <span className="truncate font-display text-[12px] uppercase tracking-[0.1em] text-slate-300 group-hover:text-neon-ice">
          {scenario.title}
        </span>
        <DataSourceBadge source={scenario.data_source} />
      </div>
      <div className="mt-0.5 flex items-center gap-1.5 text-[8px] uppercase tracking-[0.14em] text-slate-600">
        <span className="font-mono">{scenario.fault_type}</span>
        <span className="mx-1 text-neon-cyan/40">→</span>
        <span className="font-mono">{scenario.target_service}</span>
        <span className="ml-auto text-slate-500">{scenario.severity}</span>
      </div>
      <div className="mt-1 text-[9px] leading-[1.3] text-slate-500 truncate max-w-[220px]">
        {scenario.source_url}
      </div>
    </button>
  );
}

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
  const scenarios = useChaosStore((state) => state.scenarios);
  const selectedScenarioId = useChaosStore((state) => state.selectedScenarioId);
  const running = useChaosStore((state) => state.running);
  const collecting = useChaosStore((state) => state.collecting);
  const applyFixes = useChaosStore((state) => state.applyFixes);
  const setApplyFixes = useChaosStore((state) => state.setApplyFixes);
  const lastError = useChaosStore((state) => state.lastError);
  const runExperiment = useChaosStore((state) => state.runExperiment);
  const collectData = useChaosStore((state) => state.collectData);
  const experiments = useChaosStore((state) => state.experiments);
  const busy = running || collecting;

  const selectedScenario = scenarios.find((s) => s.id === selectedScenarioId);

  return (
    <Panel
      title="Control"
      code="inject"
      actions={
        <span className="text-[8px] uppercase tracking-[0.2em] text-slate-600">
          {scenarios.length} scenarios
        </span>
      }
      bodyClassName="flex flex-col gap-4 p-3"
    >
      {/* Data collection */}
      <div>
        <label className="hud-label mb-1.5 block" htmlFor="collect-btn">
          data source
        </label>
        <button
          id="collect-btn"
          type="button"
          onClick={() => void collectData()}
          disabled={busy}
          className={`group relative w-full overflow-hidden border px-3 py-3 text-center transition ${
            collecting
              ? "cursor-wait border-neon-amber/50 bg-neon-amber/10 text-neon-amber"
              : busy
                ? "cursor-wait border-slate-700 bg-void-900/60 text-slate-500"
                : "border-neon-mint/50 bg-neon-mint/[0.07] text-neon-mint hover:bg-neon-mint/[0.14] hover:shadow-mint"
          }`}
        >
          <span className="hud-corner hud-corner-tl !border-neon-mint/80" aria-hidden />
          <span className="hud-corner hud-corner-tr !border-neon-mint/80" aria-hidden />
          <span className="hud-corner hud-corner-bl !border-neon-mint/80" aria-hidden />
          <span className="hud-corner hud-corner-br !border-neon-mint/80" aria-hidden />

          <span className="flex items-center justify-center gap-2 font-display text-[17px] font-bold uppercase tracking-[0.32em]">
            {collecting ? (
              <Radar className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <RefreshCw className="h-4 w-4" aria-hidden />
            )}
            {collecting ? "collecting" : "collect data"}
          </span>
          <span className="mt-0.5 block text-[8px] uppercase tracking-[0.28em] opacity-60">
            {collecting
              ? "agent building scenarios"
              : "build scenarios from public data sources"}
          </span>
        </button>
      </div>

      {/* Scenario list */}
      <div className="min-h-[200px]">
        <div className="flex items-center justify-between mb-1.5">
          <span className="hud-label">scenarios</span>
          <span className="text-[9px] text-slate-500 uppercase tracking-[0.1em]">
            pick one to run
          </span>
        </div>
        <div className="max-h-[150px] overflow-y-auto border border-neon-cyan/10 bg-void-950/50 rounded">
          {scenarios.length === 0 ? (
            <p className="px-2 py-6 text-center text-[10px] uppercase tracking-[0.16em] text-slate-600">
              no scenarios // press "collect data"
            </p>
          ) : (
            <div className="divide-y divide-neon-cyan/[0.06]">
              {scenarios.map((scenario) => (
                <ScenarioRow key={scenario.id} scenario={scenario} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Selected scenario + run */}
      <div>
        <label className="hud-label mb-1.5 block" htmlFor="run-btn">
          run scenario
        </label>
        {selectedScenario ? (
          <div className="border border-neon-cyan/20 bg-neon-cyan/[0.04] px-2 py-2 rounded mb-2">
            <div className="flex items-center justify-between gap-2 text-[8px] uppercase tracking-[0.16em]">
              <span className="text-neon-cyan/80">selected</span>
              <DataSourceBadge source={selectedScenario.data_source} />
            </div>
            <div className="mt-1 font-mono text-[11px] text-slate-300">
              {selectedScenario.fault_type}
              <span className="text-neon-cyan/40">→</span>{" "}
              {selectedScenario.target_service}
            </div>
            <p className="mt-1 text-[9.5px] leading-[1.5] text-slate-500">
              {selectedScenario.title}
            </p>
          </div>
        ) : null}

        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 cursor-pointer select-none text-[9px] uppercase tracking-[0.12em] text-slate-500">
            <input
              type="checkbox"
              checked={applyFixes}
              onChange={() => void setApplyFixes(!applyFixes)}
              className="rounded border-slate-600 bg-void-900 text-neon-cyan focus:ring-neon-cyan"
            />
            resilient (fixes on)
          </label>
        </div>

        <button
          id="run-btn"
          type="button"
          onClick={() =>
            selectedScenarioId != null &&
            void runExperiment({ scenario_id: selectedScenarioId, fixes: applyFixes })
          }
          disabled={busy || selectedScenarioId == null}
          className={`group relative w-full overflow-hidden border px-3 py-3 text-center transition ${
            running
              ? "cursor-wait border-neon-amber/50 bg-neon-amber/10 text-neon-amber"
              : busy || selectedScenarioId == null
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
            {running ? "running" : "run scenario"}
          </span>
          <span className="mt-0.5 block text-[8px] uppercase tracking-[0.28em] opacity-60">
            {running ? "experiment in progress" : selectedScenarioId == null ? "select a scenario" : "run experiment"}
          </span>
        </button>

        {lastError ? (
          <p className="mt-1 border border-neon-red/25 bg-neon-red/[0.05] px-2 py-1.5 text-[9px] uppercase tracking-[0.1em] text-neon-red/80">
            {lastError}
          </p>
        ) : null}
      </div>

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
