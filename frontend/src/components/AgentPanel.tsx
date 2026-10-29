import { useEffect, useState } from "react";
import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  Loader2,
  ShieldAlert,
  Wrench,
} from "lucide-react";
import { api } from "../lib/api";
import type { Incident, LLMStatus } from "../types/api";
import { formatRelative } from "../lib/format";

interface AgentPanelProps {
  selectedService: string;
  incidents: Incident[];
  llm: LLMStatus;
  onDiagnosed: () => Promise<void>;
}

export function AgentPanel({
  selectedService,
  incidents,
  llm,
  onDiagnosed,
}: AgentPanelProps) {
  const [latest, setLatest] = useState<Incident | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setLatest(null), [selectedService]);

  const report = latest ?? incidents[0] ?? null;

  const diagnose = async () => {
    setBusy(true);
    setError(null);
    try {
      const incident = await api.diagnose(selectedService);
      setLatest(incident);
      await onDiagnosed();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Diagnosis failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Bot className="h-4 w-4 text-cyan-300" aria-hidden />
          Target <span className="font-medium text-slate-300">{selectedService}</span>
          <span className="chip border-white/10 bg-white/5 text-[10px] text-slate-400">
            {llm.provider} · {llm.mode}
          </span>
        </div>
        <button
          type="button"
          onClick={() => void diagnose()}
          disabled={busy}
          className="btn border-cyan-400/30 bg-cyan-400/10 text-cyan-200 hover:border-cyan-300/60 hover:bg-cyan-400/15 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BrainCircuit className="h-3.5 w-3.5" />}
          {busy ? "Analysing…" : "Diagnose"}
        </button>
      </div>

      {error ? <p className="text-xs text-rose-300">{error}</p> : null}

      {!report ? (
        <div className="rounded-lg border border-dashed border-white/10 px-4 py-10 text-center">
          <Bot className="mx-auto h-6 w-6 text-slate-600" aria-hidden />
          <p className="mt-2 text-sm text-slate-400">No incident report yet</p>
          <p className="mx-auto mt-1 max-w-sm text-xs text-slate-600">
            Diagnose a service to combine its telemetry, anomalies and fault timeline into a
            grounded explanation.
          </p>
        </div>
      ) : (
        <article className="rounded-lg border border-white/5 bg-white/[0.02] p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-white">{report.service_id}</span>
                <span className="chip border-violet-500/30 bg-violet-500/10 text-[10px] text-violet-200">
                  {report.provider}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {formatRelative(report.created_at)} · confidence {(report.confidence * 100).toFixed(0)}%
              </p>
            </div>
            <span className="font-mono text-[10px] text-slate-600">{report.id}</span>
          </div>

          <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-violet-400"
              style={{ width: `${Math.max(4, report.confidence * 100)}%` }}
            />
          </div>

          <p className="mt-4 text-sm leading-relaxed text-slate-200">{report.summary}</p>

          <div className="mt-3 rounded-md border border-amber-500/20 bg-amber-500/5 p-3">
            <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-amber-300">
              <ShieldAlert className="h-3 w-3" /> Root cause
            </p>
            <p className="mt-1 text-xs leading-relaxed text-amber-100/90">{report.root_cause}</p>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
                Evidence
              </p>
              <ul className="mt-2 space-y-1.5">
                {report.evidence.map((item, index) => (
                  <li key={`${report.id}-evidence-${index}`} className="flex gap-1.5 text-xs text-slate-400">
                    <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-cyan-400/70" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                <Wrench className="h-3 w-3" /> Recommendations
              </p>
              <ol className="mt-2 space-y-1.5">
                {report.recommendations.map((item, index) => (
                  <li key={`${report.id}-rec-${index}`} className="flex gap-2 text-xs text-slate-400">
                    <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded bg-white/5 font-mono text-[9px] text-slate-500">
                      {index + 1}
                    </span>
                    {item}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </article>
      )}
    </div>
  );
}
