import { FileWarning } from "lucide-react";
import type { Incident } from "../types/api";
import { formatRelative } from "../lib/format";

interface IncidentHistoryProps {
  incidents: Incident[];
}

export function IncidentHistory({ incidents }: IncidentHistoryProps) {
  if (incidents.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-white/10 px-4 py-8 text-center">
        <FileWarning className="mx-auto h-5 w-5 text-slate-600" aria-hidden />
        <p className="mt-2 text-xs text-slate-500">Incident reports will appear here.</p>
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {incidents.map((incident) => (
        <li key={incident.id} className="rounded-md border border-white/5 bg-white/[0.02] px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-slate-200">{incident.service_id}</span>
            <span className="text-[10px] text-slate-600">{formatRelative(incident.created_at)}</span>
          </div>
          <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-slate-500">
            {incident.summary}
          </p>
          <div className="mt-1.5 flex items-center gap-2">
            <span className="rounded border border-white/10 px-1 py-0.5 text-[9px] uppercase text-slate-500">
              {incident.provider}
            </span>
            <span className="text-[9px] text-slate-600">
              confidence {(incident.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
