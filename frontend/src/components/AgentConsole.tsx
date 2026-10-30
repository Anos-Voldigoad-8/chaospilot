import { useEffect, useRef } from "react";
import { useChaosStore } from "../store/useChaosStore";
import { formatClock } from "../lib/stats";
import { Panel } from "./Panel";
import type { LogLevel } from "../types/chaos";

const LEVEL_STYLE: Record<LogLevel, { tag: string; tagClass: string; textClass: string }> = {
  info: { tag: "info", tagClass: "text-neon-cyan/60", textClass: "text-slate-400" },
  success: { tag: "ok", tagClass: "text-neon-mint", textClass: "text-neon-mint/85" },
  warn: { tag: "warn", tagClass: "text-neon-amber", textClass: "text-neon-amber/90" },
  error: { tag: "err", tagClass: "text-neon-red", textClass: "text-neon-red/90" },
};

export function AgentConsole() {
  const logs = useChaosStore((state) => state.logs);
  const scrollerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const scroller = scrollerRef.current;
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  }, [logs.length]);

  return (
    <Panel
      title="Agent console"
      code="event stream"
      actions={
        <span className="flex items-center gap-1.5 text-[8px] uppercase tracking-[0.16em] text-slate-600">
          <span className="h-1 w-1 animate-pulse rounded-full bg-neon-mint" />
          auto-scroll
        </span>
      }
      bodyClassName="p-0"
    >
      <div
        ref={scrollerRef}
        className="h-[228px] overflow-y-auto bg-void-950/60 px-2 py-2"
      >
        {logs.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <span className="text-[10px] uppercase tracking-[0.24em] text-slate-600">
              console idle
            </span>
            <span className="text-[9px] uppercase tracking-[0.14em] text-slate-700">
              run an experiment to stream agent events
            </span>
          </div>
        ) : (
          logs.map((line) => {
            const style = LEVEL_STYLE[line.level];
            return (
              <div
                key={line.id}
                className="flex gap-2 px-1 py-[2px] leading-[1.45] transition-colors hover:bg-neon-cyan/[0.04]"
              >
                <span className="shrink-0 text-[10px] text-slate-700">{formatClock(line.at)}</span>
                <span className={`w-8 shrink-0 text-[10px] uppercase ${style.tagClass}`}>
                  {style.tag}
                </span>
                <span className={`min-w-0 break-words text-[11px] ${style.textClass}`}>
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
