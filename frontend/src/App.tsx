import { useEffect, useState } from "react";
import { AlertTriangle, Radar } from "lucide-react";
import { AgentPanel } from "./components/AgentPanel";
import { AnomalyFeed } from "./components/AnomalyFeed";
import { FaultPanel } from "./components/FaultPanel";
import { Header } from "./components/Header";
import { IncidentHistory } from "./components/IncidentHistory";
import { MetricsChart } from "./components/MetricsChart";
import { Panel } from "./components/Panel";
import { SummaryCards } from "./components/SummaryCards";
import { Topology } from "./components/Topology";
import { useDashboard } from "./hooks/useDashboard";
import { useMetrics } from "./hooks/useMetrics";
import { api } from "./lib/api";

export default function App() {
  const { data, error, loading, refresh } = useDashboard(5000);
  const [selectedService, setSelectedService] = useState("checkout");
  const [scanning, setScanning] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const metrics = useMetrics(selectedService, 15);

  useEffect(() => {
    if (data && !data.services.some((service) => service.id === selectedService)) {
      setSelectedService(data.services[0]?.id ?? "checkout");
    }
  }, [data, selectedService]);

  const scan = async () => {
    setScanning(true);
    setActionMessage(null);
    try {
      const result = await api.detect();
      setActionMessage(
        result.detected > 0
          ? `${result.detected} new anomal${result.detected === 1 ? "y" : "ies"} detected`
          : "No new anomalies above the learned baseline",
      );
      await refresh();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Detection failed");
    } finally {
      setScanning(false);
    }
  };

  if (!data) {
    return (
      <div className="min-h-screen bg-ink-950">
        <div className="mx-auto max-w-[1600px] px-4 py-6 lg:px-8">
          <Header data={null} error={error} onRefresh={() => void refresh()} />
          <div className="mt-16 text-center">
            {loading && !error ? (
              <>
                <Radar className="mx-auto h-8 w-8 animate-pulse text-cyan-400" aria-hidden />
                <p className="mt-3 text-sm text-slate-400">Connecting to the ChaosPilot backend…</p>
                <p className="mt-1 text-xs text-slate-600">
                  Start it with <code className="font-mono">uvicorn app:app --port 8090</code>
                </p>
              </>
            ) : (
              <>
                <AlertTriangle className="mx-auto h-8 w-8 text-rose-400" aria-hidden />
                <p className="mt-3 text-sm text-rose-200">Backend unreachable</p>
                <p className="mt-1 text-xs text-slate-500">{error}</p>
                <button
                  type="button"
                  onClick={() => void refresh()}
                  className="btn mx-auto mt-4 border-white/10 bg-white/5 text-slate-300"
                >
                  Retry
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-ink-950">
      <div className="mx-auto max-w-[1600px] px-4 py-6 lg:px-8">
        <Header data={data} error={error} onRefresh={() => void refresh()} />

        {error ? (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-200">
            <AlertTriangle className="h-3.5 w-3.5" />
            Showing the last successful snapshot. {error}
          </div>
        ) : null}

        <SummaryCards summary={data.summary} />

        <div className="mt-6 grid gap-5 xl:grid-cols-3">
          <Panel
            title="Service topology"
            subtitle="Click a node to focus metrics, faults and diagnosis"
            className="xl:col-span-2"
          >
            <Topology
              services={data.services}
              selectedService={selectedService}
              onSelect={setSelectedService}
            />
          </Panel>

          <Panel title="Chaos console" subtitle="Inject a fault, then watch the telemetry react">
            <FaultPanel
              services={data.services}
              selectedService={selectedService}
              activeFaults={data.active_faults}
              onChanged={refresh}
            />
          </Panel>

          <Panel
            title="Telemetry"
            subtitle={`15 minute window · ${selectedService}`}
            className="xl:col-span-2"
          >
            <MetricsChart
              services={data.services}
              selectedService={selectedService}
              onSelect={setSelectedService}
              points={metrics.points}
              loading={metrics.loading}
              error={metrics.error}
            />
          </Panel>

          <Panel
            title="Anomaly feed"
            subtitle={
              actionMessage ??
              "Isolation Forest + robust deviation scoring on the latest samples"
            }
            actions={
              <button
                type="button"
                onClick={() => void scan()}
                disabled={scanning}
                className="btn border-white/10 bg-white/5 text-slate-300 hover:border-cyan-400/30 hover:text-cyan-200 disabled:opacity-50"
              >
                <Radar className={`h-3.5 w-3.5 ${scanning ? "animate-pulse" : ""}`} />
                {scanning ? "Scanning…" : "Scan now"}
              </button>
            }
          >
            <AnomalyFeed anomalies={data.anomalies} />
          </Panel>

          <Panel
            title="Incident analyst"
            subtitle="Grounded diagnosis from metrics, anomalies and the fault timeline"
            className="xl:col-span-2"
          >
            <AgentPanel
              selectedService={selectedService}
              incidents={data.incidents}
              llm={data.llm}
              onDiagnosed={refresh}
            />
          </Panel>

          <Panel title="Incident history" subtitle="Most recent reports stored in SQLite">
            <IncidentHistory incidents={data.incidents} />
          </Panel>
        </div>

        <footer className="mt-8 flex flex-col items-start justify-between gap-2 border-t border-white/5 pt-4 text-[11px] text-slate-600 sm:flex-row sm:items-center">
          <span>
            ChaosPilot · local chaos engineering lab ·{" "}
            {data.llm.provider === "ollama" ? "Ollama" : "hosted LLM"} calls stay in the backend
          </span>
          <span>No secrets in the browser · telemetry stored in SQLite</span>
        </footer>
      </div>
    </div>
  );
}
