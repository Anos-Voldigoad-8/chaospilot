import type { ReactNode } from "react";

interface PanelProps {
  title: string;
  code?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function Panel({
  title,
  code,
  actions,
  children,
  className = "",
  bodyClassName = "p-3",
}: PanelProps) {
  return (
    <section className={`hud-panel flex min-w-0 flex-col ${className}`}>
      <span className="hud-corner hud-corner-tl" aria-hidden />
      <span className="hud-corner hud-corner-tr" aria-hidden />
      <span className="hud-corner hud-corner-bl" aria-hidden />
      <span className="hud-corner hud-corner-br" aria-hidden />

      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-neon-cyan/10 px-3 py-2">
        <div className="flex min-w-0 items-baseline gap-2">
          <h2 className="truncate font-display text-[13px] font-semibold uppercase tracking-[0.2em] text-neon-ice">
            {title}
          </h2>
          {code ? (
            <span className="hidden shrink-0 text-[9px] uppercase tracking-[0.18em] text-neon-cyan/35 sm:inline">
              {code}
            </span>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </header>

      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
