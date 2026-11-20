import { useEffect, useRef, useState, useMemo } from "react";
import { useChaosStore } from "../store/useChaosStore";
import { formatClock } from "../lib/stats";
import { Panel } from "./Panel";
import type { LogLevel } from "../types/chaos";
import { Terminal, Copy, Check, ArrowDown } from "lucide-react";
import { audioEngine } from "../lib/audio";

const LEVEL_STYLE: Record<LogLevel, { tag: string; tagClass: string; textClass: string }> = {
  info: { tag: "INFO", tagClass: "text-[#5B6272] bg-[#F8F9FB] border-[#DDE1EA]", textClass: "text-gunmetal-900" },
  success: { tag: "RECOV", tagClass: "text-emerald-700 bg-emerald-50 border-emerald-200 font-bold", textClass: "text-emerald-700 font-bold" },
  warn: { tag: "WARN", tagClass: "text-red-700 bg-red-50 border-red-200 font-semibold", textClass: "text-red-700 font-semibold" },
  error: { tag: "FAULT", tagClass: "text-red-700 bg-red-50 border-red-200 font-bold", textClass: "text-red-700 font-bold" },
};

export function AgentConsole() {
  const [filter, setFilter] = useState<string>("all");
  const [copied, setCopied] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logs = useChaosStore((state) => state.logs);
  const scrollerRef = useRef<HTMLDivElement>(null);

  const filteredLogs = useMemo(() => {
    if (filter === "all") return logs;
    return logs.filter((l) => l.level === filter);
  }, [logs, filter]);

  useEffect(() => {
    if (!autoScroll) return;
    const scroller = scrollerRef.current;
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  }, [filteredLogs.length, autoScroll]);

  const copyAll = () => {
    audioEngine.playClick();
    const text = logs.map((l) => `[${formatClock(l.at)}] [${l.level.toUpperCase()}] ${l.text}`).join("\n");
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Panel
      title="Agent Reasoning & Logs"
      code="TERMINAL STREAM"
      actions={
        <div className="flex items-center gap-2">
          {/* Filter pills */}
          <div className="flex items-center gap-1 border border-[#DDE1EA] bg-[#F8F9FB] p-0.5 font-mono text-[7.5px] uppercase">
            {["all", "info", "warn", "error"].map((lvl) => (
              <button
                key={lvl}
                type="button"
                onClick={() => {
                  audioEngine.playClick();
                  setFilter(lvl);
                }}
                className={`px-1.5 py-0.5 font-bold transition ${
                  filter === lvl
                    ? "bg-gradient-to-r from-ultraviolet to-ultraviolet-deep text-white shadow-ultravioletSm"
                    : "text-gunmetal-500 hover:bg-gunmetal-800 hover:text-white"
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={copyAll}
            className="flex items-center gap-1 border border-[#DDE1EA] bg-[#F8F9FB] px-2 py-0.5 font-mono text-[8px] font-bold uppercase tracking-wider text-gunmetal-500 hover:text-ultraviolet hover:border-ultraviolet/40 shadow-metal transition-colors"
            title="Copy logs to clipboard"
          >
            {copied ? <Check className="h-2.5 w-2.5 text-ultraviolet" /> : <Copy className="h-2.5 w-2.5" />}
            <span>{copied ? "COPIED" : "COPY"}</span>
          </button>
        </div>
      }
      bodyClassName="p-0 overflow-hidden flex flex-col font-mono"
    >
      <div className="bg-[#2B303B] px-3 py-1.5 border-b border-[#1E222B] flex items-center justify-between font-mono text-[8px] uppercase tracking-wider text-gunmetal-400 font-bold">
        <span className="flex items-center gap-1.5 text-white">
          <Terminal className="h-3 w-3 text-ultraviolet" />
          AGENT_REASONING // STREAM_ACTIVE
        </span>
        <button
          type="button"
          onClick={() => setAutoScroll(!autoScroll)}
          className={`flex items-center gap-1 font-bold ${autoScroll ? "text-ultraviolet" : "text-gunmetal-400"}`}
        >
          <ArrowDown className={`h-2.5 w-2.5 ${autoScroll ? "animate-bounce" : ""}`} />
          <span>AUTO-SCROLL</span>
        </button>
      </div>

      <div
        ref={scrollerRef}
        className="h-[210px] overflow-y-auto bg-[#F8F9FB]/60 p-2 font-mono divide-y divide-[#DDE1EA]"
      >
        {filteredLogs.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-gunmetal-500">
            <Terminal className="h-6 w-6 text-gunmetal-400" />
            <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-gunmetal-500">
              AGENT REASONING LISTENING...
            </span>
            <span className="text-[8.5px] uppercase tracking-[0.1em] text-gunmetal-500">
              INJECT A FAULT TO STREAM REAL-TIME TELEMETRY EVIDENCE
            </span>
          </div>
        ) : (
          filteredLogs.map((line) => {
            const style = LEVEL_STYLE[line.level] || LEVEL_STYLE.info;
            return (
              <div
                key={line.id}
                className="flex items-start gap-2 px-1.5 py-1 leading-relaxed hover:bg-[#F8F9FB] transition-colors"
              >
                <span className="shrink-0 text-[9px] text-[#5B6272] font-bold">
                  {formatClock(line.at)}
                </span>
                <span className={`shrink-0 px-1 py-0.2 border text-[8px] font-bold uppercase ${style.tagClass}`}>
                  {style.tag}
                </span>
                <span className={`min-w-0 break-words text-[10.5px] ${style.textClass}`}>
                  {line.text}
                </span>
              </div>
            );
          })
        )}
      </div>
    </Panel>
  );
}
