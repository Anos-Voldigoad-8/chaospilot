import { useCountUp } from "../hooks/useAnimation";
import { scoreColor, scoreVerdict } from "../lib/theme";

const ARC = "M 30.72 140 A 80 80 0 1 1 169.28 140";
const CX = 100;
const CY = 100;
const RADIUS = 80;

function tick(angle: number): string {
  const radians = (angle * Math.PI) / 180;
  const inner = RADIUS + 6;
  const outer = RADIUS + 10;
  const x1 = CX + Math.cos(radians) * inner;
  const y1 = CY + Math.sin(radians) * inner;
  const x2 = CX + Math.cos(radians) * outer;
  const y2 = CY + Math.sin(radians) * outer;
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} L ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

const TICKS = Array.from({ length: 17 }, (_, index) => 150 + index * 15);

export function ResilienceGauge({ score }: { score: number }) {
  const display = useCountUp(score);
  const color = scoreColor(display);
  const verdict = scoreVerdict(display);

  return (
    <div className="relative mx-auto w-full max-w-[248px]">
      <svg viewBox="0 0 200 158" className="w-full" role="img" aria-label={`Resilience ${Math.round(display)} of 100`}>
        <defs>
          <filter id="gauge-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {TICKS.map((angle) => (
          <path
            key={angle}
            d={tick(angle)}
            stroke="rgba(32,231,222,0.18)"
            strokeWidth="0.8"
          />
        ))}

        <path
          d={ARC}
          fill="none"
          stroke="rgba(32,231,222,0.09)"
          strokeWidth="8"
        />
        <path
          d={ARC}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="butt"
          pathLength={100}
          strokeDasharray="100"
          strokeDashoffset={100 - display}
          filter="url(#gauge-glow)"
        />

        <text x="24" y="153" fill="rgba(148,163,184,0.4)" fontSize="7" fontFamily="JetBrains Mono, monospace">
          0
        </text>
        <text x="168" y="153" fill="rgba(148,163,184,0.4)" fontSize="7" fontFamily="JetBrains Mono, monospace">
          100
        </text>
      </svg>

      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pt-2">
        <span
          className="font-display text-[44px] font-bold leading-none tabular-nums"
          style={{ color, textShadow: `0 0 18px ${color}66` }}
        >
          {Math.round(display)}
        </span>
        <span className="mt-1 text-[8px] uppercase tracking-[0.3em] text-neon-cyan/45">
          resilience
        </span>
        <span
          className="mt-1 text-[9px] uppercase tracking-[0.22em]"
          style={{ color }}
        >
          {verdict}
        </span>
      </div>
    </div>
  );
}
