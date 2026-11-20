import React, { useRef, useState } from "react";

interface SpotlightCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  spotlightColor?: string;
  borderColor?: string;
}

export function SpotlightCard({
  children,
  className = "",
  spotlightColor = "rgba(99, 102, 241, 0.14)",
  borderColor = "rgba(99, 102, 241, 0.35)",
  ...props
}: SpotlightCardProps) {
  const divRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!divRef.current) return;
    const rect = divRef.current.getBoundingClientRect();
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const handleMouseEnter = () => setOpacity(1);
  const handleMouseLeave = () => setOpacity(0);

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`relative overflow-hidden border border-gunmetal-900/15 bg-[#F8F9FB]/98 shadow-card backdrop-blur-md transition-all duration-200 ${className}`}
      {...props}
    >
      {/* Radial spotlight follow effect in Soft Ultraviolet */}
      <div
        className="pointer-events-none absolute -inset-px transition-opacity duration-300"
        style={{
          opacity,
          background: `radial-gradient(400px circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 80%)`,
        }}
        aria-hidden
      />
      {/* Dynamic border illumination */}
      <div
        className="pointer-events-none absolute -inset-px transition-opacity duration-300"
        style={{
          opacity,
          border: `1px solid ${borderColor}`,
          maskImage: `radial-gradient(220px circle at ${position.x}px ${position.y}px, black, transparent 75%)`,
          WebkitMaskImage: `radial-gradient(220px circle at ${position.x}px ${position.y}px, black, transparent 75%)`,
        }}
        aria-hidden
      />

      <div className="relative z-10">{children}</div>
    </div>
  );
}
