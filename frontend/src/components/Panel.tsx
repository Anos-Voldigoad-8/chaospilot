import { useState, useRef, type ReactNode, type MouseEvent } from "react";

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
  bodyClassName = "p-3.5",
}: PanelProps) {
  const panelRef = useRef<HTMLElement>(null);
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: MouseEvent<HTMLElement>) => {
    if (!panelRef.current) return;
    const rect = panelRef.current.getBoundingClientRect();
    setCursorPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <section
      ref={panelRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`hud-panel relative flex min-w-0 flex-col overflow-hidden border border-gunmetal-900/15 bg-[#F8F9FB]/98 shadow-card backdrop-blur-md transition-all duration-200 hover:border-gunmetal-900/30 ${className}`}
    >
      {/* Soft Ultraviolet radial cursor ambient spotlight (Glow tint: rgba(99,102,241,0.14)) */}
      <div
        className="pointer-events-none absolute -inset-px transition-opacity duration-300 z-0"
        style={{
          opacity: isHovered ? 1 : 0,
          background: `radial-gradient(380px circle at ${cursorPos.x}px ${cursorPos.y}px, rgba(99, 102, 241, 0.14), transparent 75%)`,
        }}
        aria-hidden
      />

      {/* Deep Gunmetal & Cool Titanium Header */}
      <header className="relative z-10 flex shrink-0 items-center justify-between gap-3 border-b border-titanium-shadow/70 bg-titanium-highlight/90 px-3.5 py-2.5">
        <div className="flex min-w-0 items-baseline gap-2.5">
          <h2 className="truncate font-display text-[14px] font-bold uppercase tracking-[0.14em] text-[#1E222B]">
            {title}
          </h2>
          {code ? (
            <span className="hidden shrink-0 font-mono text-[8.5px] uppercase tracking-[0.18em] text-[#5B6272] sm:inline">
              // {code}
            </span>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </header>

      <div className={`relative z-10 min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
