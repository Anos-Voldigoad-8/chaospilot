import { Activity, RefreshCw, Wifi, WifiOff } from "lucide-react";
import type { Overview } from "../types/api";
import { formatClock } from "../lib/format";

interface HeaderProps {
  data: Overview | null;
  error: string | null;
  onRefresh: () => void;
}

export function Header({ data, error, onRefresh }: HeaderProps) {
  const online = Boolean(data) && !error;
  const mode = data?.llm.mode ?? "unknown";

  return (
    <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div className="flex items-center gap-3">
        <div className="grid h-11 w-11 place-items-center rounded-xl border border-cyan-400/30 bg-cyan-400/10 text-cyan-300 shadow-glow">
          <Activity className="h-5 w-5" aria-hidden />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight text-white">ChaosPilot</h1>
            <span className="rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-slate-400">
              lab
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Inject faults · detect anomalies · explain the failure
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`chip ${
            online
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-rose-500/30 bg-rose-500/10 text-rose-300"
          }`}
        >
          {online ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
          {online ? "Backend connected" : "Backend offline"}
        </span>
        <span className="chip border-cyan-500/20 bg-cyan-500/5 text-cyan-300">
          {data?.llm.provider ?? "llm"} · {mode}
        </span>
        <span className="chip border-white/10 bg-white/5 text-slate-400">
          {data?.generated_at ? `updated ${formatClock(data.generated_at)}` : "waiting…"}
        </span>
        <button
          type="button"
          onClick={onRefresh}
          className="btn border-white/10 bg-white/5 text-slate-300 hover:border-cyan-400/30 hover:text-cyan-200"
          title="Refresh dashboard"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>
    </header>
  );
}
