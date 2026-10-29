import { useEffect, useState, type FormEvent } from "react";
import { CircleStop, Flame, Timer, Zap } from "lucide-react";
import { api } from "../lib/api";
import type { Fault, FaultType, Service } from "../types/api";
import { formatRelative } from "../lib/format";

interface ParamConfig {
  key: string;
  label: string;
  min: number;
  max: number;
  step: number;
  defaultValue: number;
}

interface FaultOption {
  value: FaultType;
  label: string;
  description: string;
  param?: ParamConfig;
}

const FAULTS: FaultOption[] = [
  {
    value: "latency",
    label: "Latency",
    description: "Delay responses",
    param: { key: "latency_ms", label: "Added latency (ms)", min: 50, max: 60000, step: 50, defaultValue: 1200 },
  },
  {
    value: "error",
    label: "Errors",
    description: "Fail a share of requests",
    param: { key: "error_rate", label: "Error rate (0–1)", min: 0, max: 1, step: 0.05, defaultValue: 0.6 },
  },
  {
    value: "crash",
    label: "Crash",
    description: "Stop the container",
  },
  {
    value: "cpu",
    label: "CPU",
    description: "Burn CPU inside the container",
    param: { key: "cpu_percent", label: "CPU pressure (%)", min: 10, max: 100, step: 5, defaultValue: 90 },
  },
  {
    value: "memory",
    label: "Memory",
    description: "Apply a memory limit",
    param: { key: "memory_mb", label: "Memory limit (MB)", min: 64, max: 4096, step: 64, defaultValue: 512 },
  },
  {
    value: "network",
    label: "Network",
    description: "Partition the container",
    param: { key: "packet_loss", label: "Packet loss (0–1)", min: 0, max: 1, step: 0.1, defaultValue: 1 },
  },
];

interface FaultPanelProps {
  services: Service[];
  selectedService: string;
  activeFaults: Fault[];
  onChanged: () => Promise<void>;
}

export function FaultPanel({
  services,
  selectedService,
  activeFaults,
  onChanged,
}: FaultPanelProps) {
  const [serviceId, setServiceId] = useState(selectedService);
  const [faultType, setFaultType] = useState<FaultType>("latency");
  const [duration, setDuration] = useState(120);
  const [paramValue, setParamValue] = useState(1200);
  const [busy, setBusy] = useState(false);
  const [recovering, setRecovering] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setServiceId(selectedService), [selectedService]);

  const option = FAULTS.find((item) => item.value === faultType) ?? FAULTS[0];

  const chooseFault = (value: FaultType) => {
    setFaultType(value);
    const next = FAULTS.find((item) => item.value === value);
    setParamValue(next?.param?.defaultValue ?? 0);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const parameters = option.param ? { [option.param.key]: Number(paramValue) } : {};
      await api.injectFault({
        service_id: serviceId,
        fault_type: faultType,
        duration_seconds: Number(duration),
        parameters,
      });
      setMessage(`${option.label} fault injected into ${serviceId}`);
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fault injection failed");
    } finally {
      setBusy(false);
    }
  };

  const recover = async (faultId: string) => {
    setRecovering(faultId);
    setError(null);
    try {
      await api.recoverFault(faultId);
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recovery failed");
    } finally {
      setRecovering(null);
    }
  };

  return (
    <div className="space-y-5">
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label htmlFor="fault-service" className="label">Target</label>
            <select
              id="fault-service"
              className="field"
              value={serviceId}
              onChange={(event) => setServiceId(event.target.value)}
            >
              {services.map((service) => (
                <option key={service.id} value={service.id}>{service.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="fault-duration" className="label">Duration (s)</label>
            <input
              id="fault-duration"
              className="field"
              type="number"
              min={10}
              max={3600}
              value={duration}
              onChange={(event) => setDuration(Number(event.target.value))}
            />
          </div>
        </div>

        <div>
          <span className="label">Fault type</span>
          <div className="grid grid-cols-3 gap-1.5">
            {FAULTS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => chooseFault(item.value)}
                title={item.description}
                className={`rounded-md border px-1 py-1.5 text-[11px] transition ${
                  item.value === faultType
                    ? "border-rose-400/40 bg-rose-500/10 text-rose-200"
                    : "border-white/5 bg-white/[0.02] text-slate-500 hover:text-slate-300"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {option.param ? (
          <div>
            <label htmlFor="fault-param" className="label">{option.param.label}</label>
            <input
              id="fault-param"
              className="field"
              type="number"
              min={option.param.min}
              max={option.param.max}
              step={option.param.step}
              value={paramValue}
              onChange={(event) => setParamValue(Number(event.target.value))}
            />
          </div>
        ) : null}

        <button
          type="submit"
          disabled={busy}
          className="btn w-full justify-center border-rose-500/30 bg-rose-500/10 text-rose-200 hover:border-rose-400/60 hover:bg-rose-500/20 disabled:opacity-50"
        >
          <Flame className="h-3.5 w-3.5" />
          {busy ? "Injecting…" : "Inject fault"}
        </button>
        {message ? <p className="text-[11px] text-emerald-300">{message}</p> : null}
        {error ? <p className="text-[11px] text-rose-300">{error}</p> : null}
      </form>

      <div className="border-t border-white/5 pt-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Active faults
          </span>
          <Zap className="h-3.5 w-3.5 text-amber-300" aria-hidden />
        </div>
        {activeFaults.length === 0 ? (
          <p className="text-xs text-slate-600">Stack is healthy — no injected faults.</p>
        ) : (
          <ul className="space-y-2">
            {activeFaults.map((fault) => (
              <li
                key={fault.id}
                className="flex items-center justify-between gap-2 rounded-md border border-amber-500/20 bg-amber-500/5 px-2.5 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs text-amber-100">
                    {fault.fault_type} · {fault.service_id}
                  </p>
                  <p className="mt-0.5 flex items-center gap-1 text-[10px] text-slate-500">
                    <Timer className="h-2.5 w-2.5" />
                    started {formatRelative(fault.started_at)}
                    {fault.ends_at
                      ? ` · ${Math.max(0, Math.round(fault.ends_at - Date.now() / 1000))}s left`
                      : ""}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void recover(fault.id)}
                  disabled={recovering === fault.id}
                  className="btn shrink-0 border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] text-emerald-200 hover:border-emerald-400/50"
                >
                  <CircleStop className="h-3 w-3" />
                  {recovering === fault.id ? "…" : "Recover"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
