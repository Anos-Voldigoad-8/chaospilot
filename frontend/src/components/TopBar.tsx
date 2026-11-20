import { useEffect, useState } from "react";
import { Volume2, VolumeX, Shield, Radio } from "lucide-react";
import { useChaosStore } from "../store/useChaosStore";
import type { ConnectionState } from "../types/chaos";
import { AnimatedCounter } from "./common/AnimatedCounter";
import { audioEngine } from "../lib/audio";
import { scoreColor } from "../lib/theme";

const CONNECTION_META: Record<
  ConnectionState,
  { label: string; color: string; detail: string }
> = {
  live: { label: "LINK LIVE", color: "#6366F1", detail: "TELEMETRY 1Hz" },
  connecting: { label: "CONNECTING", color: "#F59E0B", detail: "OPENING WS" },
  offline: { label: "OFFLINE", color: "#EF4444", detail: "AUTO-RETRY" },
  mock: { label: "MOCK FEED", color: "#818CF8", detail: "LOCAL SEED" },
};

function ConnectionBadge() {
  const connection = useChaosStore((state) => state.connection);
  const backendDown = useChaosStore((state) => state.backendDown);
  let meta = CONNECTION_META[connection];
  if (connection === "offline" && !backendDown) {
    meta = { label: "CLOUD ACTIVE", color: "#6366F1", detail: "REST CONNECTED" };
  }

  return (
    <div className="flex items-center gap-2 border border-white/10 bg-[#2B303B] px-2.5 py-1.5 shadow-hud">
      <span className="relative flex h-2 w-2">
        <span
          className="absolute inset-0 animate-ping rounded-full opacity-70"
          style={{ backgroundColor: meta.color }}
        />
        <span
          className="relative h-2 w-2 rounded-full"
          style={{ backgroundColor: meta.color, boxShadow: `0 0 8px ${meta.color}` }}
        />
      </span>
      <div className="leading-tight font-mono">
        <div
          className="text-[9px] font-bold uppercase tracking-[0.14em]"
          style={{ color: meta.color }}
        >
          {meta.label}
        </div>
      </div>
    </div>
  );
}

function FixesToggle() {
  const applyFixes = useChaosStore((state) => state.applyFixes);
  const setApplyFixes = useChaosStore((state) => state.setApplyFixes);
  const running = useChaosStore((state) => state.running);

  const toggle = () => {
    audioEngine.playClick();
    setApplyFixes(!applyFixes);
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={applyFixes}
      aria-label="Toggle Resilient Mode"
      disabled={running}
      onClick={toggle}
      className={`group flex items-center gap-2 border px-2.5 py-1.5 font-mono text-[9px] font-bold uppercase tracking-wider transition-all shadow-hud active:scale-95 ${
        applyFixes
          ? "border-ultraviolet bg-gradient-to-r from-ultraviolet to-ultraviolet-deep text-white shadow-[0_0_12px_rgba(99,102,241,0.25)]"
          : "border-white/10 bg-[#2B303B] text-[#DDE1EA] hover:border-ultraviolet hover:text-white"
      } ${running ? "cursor-not-allowed opacity-60" : ""}`}
      title="Toggle Circuit Breakers, Timeouts, and Resilient Retries"
    >
      <Shield className="h-3 w-3" />
      <span className="hidden sm:inline">RESILIENT SHIELD:</span>
      <span>{applyFixes ? "ACTIVE" : "OFF"}</span>
    </button>
  );
}

function SoundToggle() {
  const [soundOn, setSoundOn] = useState(() => audioEngine.enabled);

  const toggle = () => {
    const next = !soundOn;
    audioEngine.setEnabled(next);
    setSoundOn(next);
    if (next) audioEngine.playClick();
  };

  return (
    <button
      type="button"
      onClick={toggle}
      className={`flex items-center gap-1.5 border px-2.5 py-1.5 font-mono text-[9px] font-semibold uppercase tracking-wider transition shadow-hud active:scale-95 ${
        soundOn
          ? "border-ultraviolet/60 bg-ultraviolet/20 text-ultraviolet-light shadow-ultravioletSm"
          : "border-white/10 bg-[#2B303B] text-[#DDE1EA] hover:border-white/25 hover:text-white"
      }`}
      title={soundOn ? "Mute audio cues" : "Enable tactile sound feedback"}
    >
      {soundOn ? <Volume2 className="h-3 w-3 text-ultraviolet-light" /> : <VolumeX className="h-3 w-3" />}
      <span className="hidden md:inline">{soundOn ? "AUDIO ON" : "MUTED"}</span>
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
    <div className="hidden border-l border-white/10 pl-3.5 text-right leading-none lg:block font-mono">
      <div className="text-[13px] font-bold tabular-nums text-white">
        {now.toLocaleTimeString("en-GB", { hour12: false })}
      </div>
      <div className="mt-1 text-[8px] uppercase tracking-[0.2em] text-[#5B6272] font-semibold">
        LOCAL TIME
      </div>
    </div>
  );
}

export function TopBar() {
  const mockMode = useChaosStore((state) => state.mockMode);
  const backendDown = useChaosStore((state) => state.backendDown);
  const running = useChaosStore((state) => state.running);
  const collecting = useChaosStore((state) => state.collecting);
  const score = useChaosStore((state) => state.score);

  return (
    <header className="sticky top-0 z-40 border-b border-black/30 bg-[#1E222B] shadow-card backdrop-blur-md">
      <div className="mx-auto flex max-w-[1780px] flex-wrap items-center justify-between gap-x-4 gap-y-2.5 px-3 py-2.5 sm:px-6">
        
        {/* Left: Deep Gunmetal & Soft Ultraviolet Brand Identity */}
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center border border-ultraviolet/80 bg-gradient-to-br from-ultraviolet to-ultraviolet-deep text-white font-mono text-[14px] font-black shadow-[0_0_12px_rgba(99,102,241,0.25)]">
            CP
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-display text-[21px] font-black leading-none tracking-[0.12em] text-white flex items-center gap-1.5">
                <span>CHAOSPILOT</span>
                <span className="h-1.5 w-1.5 rounded-full bg-ultraviolet shadow-[0_0_8px_#6366F1]" />
              </h1>
              <span className="border border-white/10 bg-[#2B303B] px-1.5 py-0.5 font-mono text-[8px] font-bold tracking-widest text-ultraviolet-light">
                3D COCKPIT
              </span>
            </div>
            <p className="mt-0.5 font-mono text-[8px] uppercase tracking-[0.24em] text-[#5B6272]">
              COOL TITANIUM SILK & DEEP GUNMETAL
            </p>
          </div>
        </div>

        {/* Center: Live Mission Status Beacon in Raised Gunmetal */}
        <div className="hidden xl:flex items-center gap-2.5 border border-white/10 bg-[#2B303B] px-3.5 py-1.5 shadow-hud">
          <Radio
            className={`h-3.5 w-3.5 ${
              running
                ? "text-signal-red animate-pulse"
                : collecting
                  ? "text-signal-amber animate-spin"
                  : "text-ultraviolet-light"
            }`}
          />
          <div className="font-mono text-[9px] uppercase tracking-[0.16em]">
            <span className="text-[#5B6272]">CLUSTER: </span>
            <span
              className={`font-bold ${
                running
                  ? "text-signal-red"
                  : collecting
                    ? "text-signal-amber"
                    : "text-ultraviolet-light"
              }`}
            >
              {running
                ? "CHAOS FAULT INJECTION ACTIVE"
                : collecting
                  ? "HARVESTING STATUS FEEDS"
                  : "NOMINAL STEADY-STATE"}
            </span>
          </div>
        </div>

        {/* Right: Telemetry & Controls */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          {/* Resilience Score Pill in Raised Gunmetal */}
          <div className="flex items-center gap-2 border border-white/10 bg-[#2B303B] px-3 py-1.5 shadow-hud">
            <span className="font-mono text-[8px] uppercase tracking-[0.14em] text-[#5B6272]">
              RESILIENCE
            </span>
            <span
              className="font-mono text-[14px] font-bold leading-none"
              style={{ color: scoreColor(score) }}
            >
              <AnimatedCounter value={score} duration={500} suffix="/100" />
            </span>
          </div>

          <SoundToggle />
          <FixesToggle />
          <ConnectionBadge />
          <Clock />
        </div>
      </div>

      {backendDown && !mockMode ? (
        <div className="border-t border-signal-red/50 bg-signal-redLight px-3 py-1.5 text-center font-mono text-[9px] font-bold uppercase tracking-[0.16em] text-signal-red">
          BACKEND DISCONNECTED // RECONNECTING TO FASTAPI
        </div>
      ) : null}
    </header>
  );
}
