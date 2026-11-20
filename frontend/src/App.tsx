import { useEffect, useRef } from "react";
import { AgentConsole } from "./components/AgentConsole";
import { ComparePanel } from "./components/ComparePanel";
import { ControlPanel } from "./components/ControlPanel";
import { LiveMetrics } from "./components/LiveMetrics";
import { PostmortemPanel } from "./components/PostmortemPanel";
import { ServiceMap } from "./components/ServiceMap";
import { TelemetryStream } from "./components/TelemetryStream";
import { TopBar } from "./components/TopBar";
import { AuroraBackground } from "./components/common/AuroraBackground";
import { useWebSocket } from "./hooks/useWebSocket";
import { useChaosStore } from "./store/useChaosStore";

export default function App() {
  useWebSocket();

  const mockMode = useChaosStore((state) => state.mockMode);
  const mockStarted = useRef(false);

  useEffect(() => {
    if (!mockMode) return;
    const timer = window.setTimeout(() => {
      if (mockStarted.current) return;
      mockStarted.current = true;
      void useChaosStore.getState().runExperiment();
    }, 700);
    return () => window.clearTimeout(timer);
  }, [mockMode]);

  return (
    <div className="min-h-screen relative overflow-x-hidden text-gunmetal-900 font-mono">
      {/* Sleek Cool Titanium & Soft Ultraviolet Ambient Aura */}
      <AuroraBackground />

      {/* Deep Gunmetal Navigation & High-Contrast Masthead */}
      <TopBar />

      <main className="relative z-10 mx-auto w-full max-w-[1780px] px-3 pb-8 pt-3 sm:px-6">
        {/* Core Deck: Mission Control, 3D Architectural Topology, and Live Telemetry */}
        <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-[330px_minmax(0,1fr)_350px]">
          <div className="order-2 min-w-0 xl:order-none">
            <ControlPanel />
          </div>
          <div className="order-1 min-w-0 md:col-span-2 xl:order-none xl:col-span-1 flex flex-col gap-3.5">
            <ServiceMap />
            <TelemetryStream />
          </div>
          <div className="order-3 min-w-0 xl:order-none xl:col-span-1">
            <LiveMetrics />
          </div>
        </div>

        {/* Intelligence Deck: Reasoning Log, AI Postmortem & RCA, and Comparative Delta */}
        <div className="mt-3.5 grid grid-cols-1 gap-3.5 lg:grid-cols-2 xl:grid-cols-[1.15fr_1.1fr_0.85fr]">
          <AgentConsole />
          <PostmortemPanel />
          <div className="min-w-0 lg:col-span-2 xl:col-span-1">
            <ComparePanel />
          </div>
        </div>

        {/* Deep Gunmetal Technical Footer */}
        <footer className="mt-8 flex flex-col items-start justify-between gap-2 border border-gunmetal-900/15 bg-gunmetal-900 p-3.5 font-mono text-[9px] uppercase tracking-[0.16em] text-gunmetal-400 sm:flex-row sm:items-center shadow-card">
          <div className="flex items-center gap-2">
            <span className="font-bold text-ultraviolet">CHAOSPILOT // COOL TITANIUM SILK & GUNMETAL</span>
            <span>·</span>
            <span className="text-white/90">{mockMode ? "MOCK REPLAY" : "BACKEND LINK :8090"}</span>
          </div>
          <div className="flex items-center gap-3 text-[#5B6272]">
            <span>DETERMINISTIC SIMULATION</span>
            <span>·</span>
            <span>ISOLATION FOREST ANOMALY RADAR</span>
            <span>·</span>
            <span>ZERO EXPOSED SECRETS</span>
          </div>
        </footer>
      </main>
    </div>
  );
}
