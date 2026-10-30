import { useEffect, useState } from "react";
import { Power } from "lucide-react";
import { useChaosStore } from "../store/useChaosStore";
import type { ConnectionState } from "../types/chaos";

const CONNECTION_META: Record<
  ConnectionState,
  { label: string; color: string; detail: string }
> = {
  live: { label: "link live", color: "#41f2a6", detail: "streaming telemetry" },
  connecting: { label: "linking", color: "#ffb224", detail: "opening websocket" },
  offline: { label: "link down", color: "#ff3d55", detail: "retrying with backoff" },
  mock: { label: "mock feed", color: "#20e7de", detail: "scripted replay" },
};

function ConnectionBadge() {
  const connection = useChaosStore((state) => state.connection);
  const meta = CONNECTION_META[connection];

  return (
    <div className="flex items-center gap-2 border border-neon-cyan/15 bg-void-900/70 px-2.5 py-1.5">
      <span className="relative flex h-2 w-2">
        <span
          className="absolute inset-0 animate-ping rounded-full opacity-60"
          style={{ backgroundColor: meta.color }}
        />
        <span
          className="relative h-2 w-2 rounded-full"
          style={{ backgroundColor: meta.color, boxShadow: `0 0 8px ${meta.color}` }}
        />
      </span>
      <div className="leading-none">
        <div
          className="text-[9px] font-semibold uppercase tracking-[0.18em]"
          style={{ color: meta.color }}
        >
          {meta.label}
        </div>
        <div className="mt-1 hidden text-[8px] uppercase tracking-[0.12em] text-slate-600 sm:block">
          {meta.detail}
        </div>
      </div>
    </div>
  );
}

function FixesToggle() {
  const applyFixes = useChaosStore((state) => state.applyFixes);
  const setApplyFixes = useChaosStore((state) => state.setApplyFixes);

  return (
    <button
      type="button"
      role="switch"
      aria-checked={applyFixes}
      aria-label="Apply fixes before the experiment"
      onClick={() => setApplyFixes(!applyFixes)}
      className={`group flex items-center gap-2 border px-2 py-1.5 transition ${
        applyFixes
          ? "border-neon-cyan/50 bg-neon-cyan/10 shadow-cyan"
          : "border-neon-cyan/15 bg-void-900/70 hover:border-neon-cyan/30"
      }`}
      title="Restart the stack with RESILIENT=true before the baseline"
    >
      <Power
        className={`h-3 w-3 ${applyFixes ? "text-neon-cyan" : "text-slate-500"}`}
        aria-hidden
      />
      <span className="hidden text-[9px] uppercase tracking-[0.18em] text-slate-400 sm:inline">
        apply fixes
      </span>
      <span
        className={`relative h-4 w-8 border transition ${
          applyFixes ? "border-neon-cyan/70 bg-neon-cyan/15" : "border-slate-600/60 bg-void-950"
        }`}
      >
        <span
          className={`absolute top-0.5 h-2.5 w-2.5 transition-all duration-200 ${
            applyFixes
              ? "left-[17px] bg-neon-cyan shadow-[0_0_8px_#20e7de]"
              : "left-0.5 bg-slate-500"
          }`}
        />
      </span>
      <span
        className={`w-5 text-[9px] font-semibold uppercase tracking-[0.1em] ${
          applyFixes ? "text-neon-cyan" : "text-slate-600"
        }`}
      >
        {applyFixes ? "on" : "off"}
      </span>
    </button>
  );
}

function Clock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="hidden text-right leading-none lg:block">
      <div className="hud-value text-[15px] font-medium">
        {now.toLocaleTimeString("en-GB", { hour12: false })}
      </div>
      <div className="mt-1 text-[8px] uppercase tracking-[0.24em] text-neon-cyan/35">
        local time
      </div>
    </div>
  );
}

export function TopBar() {
  const mockMode = useChaosStore((state) => state.mockMode);

  return (
    <header className="sticky top-0 z-40 border-b border-neon-cyan/15 bg-void-950/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1700px] flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 sm:px-4">
        <div className="flex items-center gap-2.5">
          <svg
            viewBox="0 0 32 32"
            className="h-8 w-8 shrink-0 text-neon-cyan drop-shadow-[0_0_8px_rgba(32,231,222,0.5)]"
            aria-hidden
          >
            <rect
              x="4.5"
              y="4.5"
              width="23"
              height="23"
              fill="none"
              stroke="currentColor"
              strokeWidth="0.8"
              opacity="0.35"
              transform="rotate(45 16 16)"
            />
            <rect
              x="9.5"
              y="9.5"
              width="13"
              height="13"
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
            />
            <circle cx="16" cy="16" r="2.2" fill="currentColor" />
            <path d="M16 2v3M16 27v3M2 16h3M27 16h3" stroke="currentColor" strokeWidth="1" />
          </svg>
          <div>
            <h1 className="font-display text-[21px] font-bold leading-none tracking-[0.16em] text-neon-ice text-glow">
              CHAOSPILOT
            </h1>
            <p className="mt-1 text-[8px] uppercase tracking-[0.3em] text-neon-cyan/40">
              chaos engineering console
            </p>
          </div>
        </div>

        <span
          className={`hud-chip ml-1 border-neon-cyan/25 text-neon-cyan/70 ${
            mockMode ? "" : "hidden"
          }`}
        >
          mock
        </span>

        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <ConnectionBadge />
          <FixesToggle />
          <Clock />
        </div>
      </div>
    </header>
  );
}
