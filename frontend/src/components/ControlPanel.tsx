import { useState, useMemo } from "react";
import {
  Play,
  Radar,
  RefreshCw,
  Zap,
  Flame,
  Target,
  History,
} from "lucide-react";
import { useChaosStore } from "../store/useChaosStore";
import { formatRelative } from "../lib/stats";
import { scoreColor } from "../lib/theme";
import { Panel } from "./Panel";
import { TimelineChoreographer } from "./TimelineChoreographer";
import { audioEngine } from "../lib/audio";

function DataSourceBadge({ source }: { source: string }) {
  const isLive = source === "live";
  const isCached = source === "cached";
  return (
    <span
      className={`inline-flex items-center gap-1 border px-1.5 py-0.5 font-mono text-[8px] font-bold uppercase tracking-[0.1em] ${
        isLive
          ? "border-ultraviolet/40 bg-ultraviolet/10 text-ultraviolet"
          : isCached
            ? "border-signal-amber/40 bg-signal-amberLight text-signal-amber"
            : "border-[#DDE1EA] bg-[#F8F9FB] text-[#5B6272]"
      }`}
    >
      <span
        className={`h-1 w-1 rounded-full ${
          isLive ? "bg-ultraviolet" : isCached ? "bg-signal-amber" : "bg-gunmetal-400"
        }`}
      />
      {source}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const isCritical = severity === "critical";
  const isHigh = severity === "high";
  return (
    <span
      className={`font-mono text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 border ${
        isCritical
          ? "text-signal-red bg-signal-redLight border-signal-red/30"
          : isHigh
            ? "text-signal-amber bg-signal-amberLight border-signal-amber/30"
            : "text-[#5B6272] bg-[#F8F9FB] border-[#DDE1EA]"
      }`}
    >
      {severity}
    </span>
  );
}

export function ControlPanel() {
  const [filterFault, setFilterFault] = useState<string>("all");
  const scenarios = useChaosStore((state) => state.scenarios);
  const selectedScenarioId = useChaosStore((state) => state.selectedScenarioId);
  const selectScenario = useChaosStore((state) => state.selectScenario);
  const running = useChaosStore((state) => state.running);
  const faultActive = useChaosStore((state) => state.faultActive);
  const collecting = useChaosStore((state) => state.collecting);
  const applyFixes = useChaosStore((state) => state.applyFixes);
  const setApplyFixes = useChaosStore((state) => state.setApplyFixes);
  const lastError = useChaosStore((state) => state.lastError);
  const runExperiment = useChaosStore((state) => state.runExperiment);
  const resolveExperiment = useChaosStore((state) => state.resolveExperiment);
  const collectData = useChaosStore((state) => state.collectData);
  const experiments = useChaosStore((state) => state.experiments);
  const loadExperiment = useChaosStore((state) => state.loadExperiment);
  const busy = running || collecting;

  const filteredScenarios = useMemo(() => {
    if (filterFault === "all") return scenarios;
    return scenarios.filter((s) => s.fault_type.toLowerCase() === filterFault.toLowerCase());
  }, [scenarios, filterFault]);

  const selectedScenario = scenarios.find((s) => s.id === selectedScenarioId);

  const handleCollect = () => {
    audioEngine.playTelemetryChirp();
    void collectData();
  };

  const handleRun = () => {
    if (selectedScenarioId != null) {
      audioEngine.playFaultAlert();
      void runExperiment({ scenario_id: selectedScenarioId, fixes: applyFixes });
    }
  };

  return (
    <Panel
      title="Chaos Control"
      code="INJECT DECK"
      actions={
        <div className="flex items-center gap-1.5 font-mono text-[8px] uppercase tracking-[0.16em] text-[#5B6272] font-semibold">
          <Zap className="h-3 w-3 text-ultraviolet" />
          <span>{scenarios.length} SCENARIOS</span>
        </div>
      }
      bodyClassName="flex flex-col gap-3 p-3.5"
    >
      {/* 1. Real-time Incident Choreography Scrubber */}
      <TimelineChoreographer />

      {/* 2. Keyless Public Incident Feed Harvester */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="font-mono text-[8.5px] uppercase tracking-[0.18em] text-[#5B6272] font-bold">
            DATA HARVESTER
          </span>
          <span className="font-mono text-[8px] uppercase tracking-wider text-[#5B6272]">
            PUBLIC STATUS APIS
          </span>
        </div>
        <button
          type="button"
          onClick={handleCollect}
          disabled={busy}
          className={`group w-full border px-3 py-2.5 text-center font-mono transition-all duration-200 shadow-metal active:scale-[0.99] ${
            collecting
              ? "cursor-wait border-signal-amber bg-signal-amberLight text-signal-amber font-bold"
              : busy
                ? "cursor-not-allowed border-gunmetal-900/10 bg-titanium-fold text-[#5B6272]"
                : "border-gunmetal-900/15 bg-[#F8F9FB] text-[#1E222B] hover:border-ultraviolet hover:bg-titanium-highlight"
          }`}
        >
          <div className="flex items-center justify-center gap-2 font-display text-[15px] font-bold uppercase tracking-[0.2em]">
            {collecting ? (
              <Radar className="h-4 w-4 animate-spin text-signal-amber" />
            ) : (
              <RefreshCw className="h-4 w-4 text-ultraviolet transition-transform group-hover:rotate-180 duration-500" />
            )}
            <span>{collecting ? "HARVESTING FEEDS..." : "HARVEST REAL INCIDENTS"}</span>
          </div>
          <span className="mt-0.5 block text-[8px] uppercase tracking-[0.2em] text-[#5B6272]">
            {collecting
              ? "SCRAPLING QUERIES STATUSPAGE · GITHUB · WEATHER"
              : "SCRAPLING AGENT WITH DETERMINISTIC SEED FALLBACK"}
          </span>
        </button>
      </div>

      {/* 3. Filterable Attack Vector Catalog */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[8.5px] uppercase tracking-[0.18em] text-[#5B6272] font-bold">
            ATTACK CATALOG
          </span>

          {/* Filter Pills */}
          <div className="flex items-center gap-1 border border-gunmetal-900/15 bg-titanium-fold/70 p-0.5">
            {["all", "latency", "kill", "memory"].map((kind) => (
              <button
                key={kind}
                type="button"
                onClick={() => {
                  audioEngine.playClick();
                  setFilterFault(kind);
                }}
                className={`px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-wider transition ${
                  filterFault === kind
                    ? "bg-[#6366F1] text-white font-bold shadow-[0_0_12px_rgba(99,102,241,0.25)]"
                    : "text-[#5B6272] hover:bg-[#2B303B] hover:text-white"
                }`}
              >
                {kind}
              </button>
            ))}
          </div>
        </div>

        {/* Scrollable Scenario List */}
        <div className="max-h-[148px] overflow-y-auto border border-gunmetal-900/15 bg-[#F8F9FB] divide-y divide-[#DDE1EA]">
          {filteredScenarios.length === 0 ? (
            <p className="px-3 py-6 text-center font-mono text-[9px] uppercase tracking-[0.2em] text-[#5B6272]">
              NO SCENARIOS LOADED // PRESS HARVEST
            </p>
          ) : (
            filteredScenarios.map((scenario) => {
              const isSelected = selectedScenarioId === scenario.id;
              return (
                <button
                  key={scenario.id}
                  type="button"
                  onClick={() => {
                    audioEngine.playClick();
                    void selectScenario(scenario.id);
                  }}
                  className={`w-full px-2.5 py-2 text-left transition-all ${
                    isSelected
                      ? "border-l-4 border-ultraviolet bg-titanium-highlight shadow-paper font-semibold"
                      : "hover:bg-titanium-highlight hover:border-l-4 hover:border-gunmetal-900/20"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="font-mono text-[9px] text-[#5B6272] font-bold">
                      #{scenario.id}
                    </span>
                    <span className="truncate font-display text-[13px] font-bold uppercase tracking-[0.08em] text-[#1E222B]">
                      {scenario.title}
                    </span>
                    <DataSourceBadge source={scenario.data_source} />
                  </div>

                  <div className="mt-1 flex items-center justify-between font-mono text-[8.5px] uppercase tracking-wider text-[#5B6272]">
                    <div className="flex items-center gap-1.5">
                      <span className="text-ultraviolet font-bold">{scenario.fault_type}</span>
                      <span className="text-[#5B6272]/50">→</span>
                      <span className="text-[#1E222B] font-bold">{scenario.target_service}</span>
                    </div>
                    <SeverityBadge severity={scenario.severity} />
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* 4. Target Armed & Soft Ultraviolet CTA Button */}
      <div className="border border-gunmetal-900/15 bg-titanium-highlight/80 p-3 shadow-card backdrop-blur-md">
        {selectedScenario ? (
          <div className="mb-3">
            <div className="flex items-center justify-between text-[8px] font-mono uppercase tracking-[0.16em]">
              <span className="flex items-center gap-1 text-ultraviolet font-bold">
                <Target className="h-3.5 w-3.5" />
                TARGET ARMED
              </span>
              <span className="text-[#5B6272] font-bold">SEV: {selectedScenario.severity.toUpperCase()}</span>
            </div>

            <div className="mt-1 font-mono text-[12px] font-bold text-[#1E222B] flex items-center gap-2">
              <span className="bg-ultraviolet/15 text-ultraviolet px-1.5 py-0.5 border border-ultraviolet/30 uppercase">
                {selectedScenario.fault_type}
              </span>
              <span className="text-[#5B6272]">targets</span>
              <span className="bg-[#F8F9FB] text-[#1E222B] px-1.5 py-0.5 border border-gunmetal-900/15 uppercase">
                {selectedScenario.target_service}
              </span>
            </div>

            <p className="mt-1.5 font-mono text-[9px] leading-relaxed text-[#5B6272] line-clamp-2">
              {selectedScenario.title}
            </p>
          </div>
        ) : (
          <div className="mb-2 text-center py-2 font-mono text-[9px] uppercase tracking-wider text-[#5B6272]">
            SELECT A VECTOR ABOVE TO ARM SIMULATION
          </div>
        )}

        {/* Resilient Checkbox Toggle with Focus Ring */}
        <label className="flex items-center gap-2 mb-3 cursor-pointer select-none font-mono text-[9px] font-bold uppercase tracking-[0.12em] text-[#1E222B] hover:text-ultraviolet">
          <input
            type="checkbox"
            checked={applyFixes}
            onChange={() => {
              audioEngine.playClick();
              void setApplyFixes(!applyFixes);
            }}
            className="h-3.5 w-3.5 rounded border-gunmetal-900/20 bg-[#F8F9FB] text-ultraviolet focus:ring-2 focus:ring-ultraviolet focus:ring-offset-1"
          />
          <span>ENABLE RESILIENT SHIELD (CIRCUIT BREAKERS & TIMEOUTS)</span>
        </label>

        {/* Resolve / Inject action button */}
        {faultActive ? (
          <button
            type="button"
            onClick={() => {
              audioEngine.playFaultAlert();
              void resolveExperiment();
            }}
            disabled={busy}
            className={`group w-full border px-4 py-3 text-center font-mono transition-all duration-200 shadow-[0_0_24px_rgba(16,185,129,0.18)] active:scale-[0.98] ${
              busy
                ? "cursor-not-allowed border-gunmetal-900/10 bg-titanium-fold text-[#5B6272] shadow-none"
                : "border-signal-green bg-gradient-to-r from-[#10B981] to-[#059669] text-white font-black hover:from-[#059669] hover:to-[#0D9488] shadow-[0_0_24px_rgba(16,185,129,0.25)] focus:ring-2 focus:ring-signal-green"
            }`}
          >
            <div className="flex items-center justify-center gap-2 font-display text-[17px] font-black uppercase tracking-[0.24em]">
              <Play className="h-5 w-5 text-white fill-current" />
              <span>{"APPLY FIX & RECOVER"}</span>
            </div>
            <span className="mt-0.5 block font-mono text-[8px] uppercase tracking-[0.22em] text-white/90 font-bold opacity-90">
              HEAL THE STACK // RESTORE NOMINAL TELEMETRY
            </span>
          </button>
        ) : (
          <button
            type="button"
            onClick={handleRun}
            disabled={busy || selectedScenarioId == null}
            className={`group w-full border px-4 py-3 text-center font-mono transition-all duration-200 shadow-[0_0_24px_rgba(99,102,241,0.14)] active:scale-[0.98] ${
              running
                ? "cursor-wait border-signal-red bg-signal-red text-white font-black animate-pulse"
                : busy || selectedScenarioId == null
                  ? "cursor-not-allowed border-gunmetal-900/10 bg-titanium-fold text-[#5B6272] shadow-none"
                  : "border-ultraviolet bg-gradient-to-r from-[#6366F1] to-[#7C3AED] text-white font-black hover:from-[#4F46E5] hover:to-[#6D28D9] shadow-[0_0_24px_rgba(99,102,241,0.2)] focus:ring-2 focus:ring-ultraviolet"
            }`}
          >
            <div className="flex items-center justify-center gap-2 font-display text-[17px] font-black uppercase tracking-[0.24em]">
              {running ? (
                <Flame className="h-5 w-5 text-white animate-bounce" />
              ) : (
                <Play className="h-5 w-5 text-white fill-current transition-transform group-hover:scale-110" />
              )}
              <span>{running ? "ATTACK UNDERWAY..." : "INJECT FAULT"}</span>
            </div>
            <span className="mt-0.5 block font-mono text-[8px] uppercase tracking-[0.22em] text-white/90 font-bold opacity-90">
              {running
                ? "WATCH 3D ARCHITECTURE & TELEMETRY"
                : selectedScenarioId == null
                  ? "SELECT VECTOR FIRST"
                  : "START 40-SECOND IN-PROCESS EXPERIMENT"}
            </span>
          </button>
        )}

        {lastError ? (
          <div className="mt-2 border border-signal-red bg-signal-redLight p-2 font-mono text-[9px] uppercase tracking-wider text-signal-red font-bold">
            {lastError}
          </div>
        ) : null}
      </div>

      {/* 5. Experiment History Log */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between font-mono text-[8.5px] uppercase tracking-[0.18em] text-[#5B6272] font-bold">
          <span className="flex items-center gap-1">
            <History className="h-3 w-3" />
            EXPERIMENT RUN LOG
          </span>
          <span>{experiments.length} RECORDED</span>
        </div>

        <div className="max-h-[130px] overflow-y-auto border border-gunmetal-900/15 bg-[#F8F9FB] divide-y divide-[#DDE1EA]">
          {experiments.length === 0 ? (
            <p className="px-3 py-4 text-center font-mono text-[9px] uppercase tracking-wider text-[#5B6272]">
              NO RUNS RECORDED
            </p>
          ) : (
            experiments.map((run) => {
              const color = scoreColor(run.score ?? 0);
              return (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => {
                    audioEngine.playClick();
                    void loadExperiment(run.id);
                  }}
                  className="group w-full px-2.5 py-1.5 text-left transition hover:bg-titanium-highlight flex items-center justify-between"
                  title="Click to view postmortem & analysis"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 font-mono text-[10px]">
                      <span className="text-[#5B6272] font-bold">#{run.id}</span>
                      <span className="font-bold text-[#1E222B]">
                        {run.fault} → {run.target}
                      </span>
                      {run.fixes ? (
                        <span className="text-[7.5px] border border-ultraviolet/40 bg-ultraviolet/10 text-ultraviolet font-bold px-1">
                          SHIELD ON
                        </span>
                      ) : null}
                    </div>
                    <div className="text-[8px] font-mono text-[#5B6272]">
                      {formatRelative(run.started)}
                    </div>
                  </div>

                  <div className="font-mono text-[13px] font-bold" style={{ color }}>
                    {run.score ?? "--"}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </Panel>
  );
}
