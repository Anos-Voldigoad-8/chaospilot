import { useEffect, useRef } from "react";
import { AgentConsole } from "./components/AgentConsole";
import { ControlPanel } from "./components/ControlPanel";
import { LiveMetrics } from "./components/LiveMetrics";
import { PostmortemPanel } from "./components/PostmortemPanel";
import { ServiceMap } from "./components/ServiceMap";
import { TopBar } from "./components/TopBar";
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
    <div className="min-h-screen">
      <div className="scanlines" aria-hidden />
      <TopBar />

      <main className="mx-auto w-full max-w-[1700px] px-2.5 pb-5 pt-3 sm:px-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-[300px_minmax(0,1fr)_340px]">
          <div className="order-2 min-w-0 xl:order-none">
            <ControlPanel />
          </div>
          <div className="order-1 min-w-0 md:col-span-2 xl:order-none xl:col-span-1">
            <ServiceMap />
          </div>
          <div className="order-3 min-w-0 xl:order-none xl:col-span-1">
            <LiveMetrics />
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[1.25fr_1fr]">
          <AgentConsole />
          <PostmortemPanel />
        </div>

        <footer className="mt-4 flex flex-col items-start justify-between gap-1 border-t border-neon-cyan/10 pt-3 text-[8px] uppercase tracking-[0.18em] text-slate-700 sm:flex-row sm:items-center">
          <span>
            chaospilot // local chaos lab //{" "}
            {mockMode ? "mock feed active" : "backend :8090"}
          </span>
          <span>telemetry in sqlite · llm calls stay in the backend</span>
        </footer>
      </main>
    </div>
  );
}
