import { scoreColor, scoreVerdict } from "../lib/theme";
import { AnimatedCounter } from "./common/AnimatedCounter";

const ARC = "M 30.72 140 A 80 80 0 1 1 169.28 140";
const CX = 100;
const CY = 100;
const RADIUS = 80;

function tick(angle: number): string {
  const radians = (angle * Math.PI) / 180;
  const inner = RADIUS + 5;
  const outer = RADIUS + 10;
  const x1 = CX + Math.cos(radians) * inner;
  const y1 = CY + Math.sin(radians) * inner;
  const x2 = CX + Math.cos(radians) * outer;
  const y2 = CY + Math.sin(radians) * outer;
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} L ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

const TICKS = Array.from({ length: 17 }, (_, index) => 150 + index * 15);

export function ResilienceGauge({ score }: { score: number }) {
  const color = scoreColor(score);
  const verdict = scoreVerdict(score);

  // Circumference calculation for strokeDashoffset (approx 335 total arc length)
  const arcLength = 335;
  const offset = arcLength - (arcLength * Math.min(100, Math.max(0, score))) / 100;

  return (
    <div className="relative mx-auto w-full max-w-[260px] py-1 select-none font-mono">
      <svg
        viewBox="0 0 200 156"
        className="w-full"
        role="img"
        aria-label={`Resilience score: ${Math.round(score)} out of 100`}
      >
        <defs>
          <filter id="ultraviolet-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Outer tick marks */}
        {TICKS.map((angle) => (
          <path
            key={angle}
            d={tick(angle)}
            stroke="rgba(99, 102, 241, 0.25)"
            strokeWidth="1.2"
          />
        ))}

        {/* Inactive background track in Cool Titanium Silk (deep shadow fold) */}
        <path
          d={ARC}
          fill="none"
          stroke="#DDE1EA"
          strokeWidth="9"
        />

        {/* Active glowing score stroke */}
        <path
          d={ARC}
          fill="none"
          stroke={color}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={arcLength}
          strokeDashoffset={offset}
          filter="url(#ultraviolet-glow)"
          className="transition-all duration-700 ease-out"
        />
      </svg>

      {/* Center readout overlay */}
      <div className="absolute inset-x-0 bottom-2.5 flex flex-col items-center justify-center text-center">
        <div className="font-mono text-[36px] font-black leading-none tracking-tight text-gunmetal-900">
          <AnimatedCounter value={score} duration={500} />
          <span className="text-[13px] font-mono text-gunmetal-500 font-normal">/100</span>
        </div>

        <div className="mt-1">
          <span
            className="inline-block border px-2 py-0.5 font-mono text-[8.5px] font-bold uppercase tracking-[0.18em]"
            style={{
              color,
              borderColor: `${color}60`,
              backgroundColor: `${color}18`,
              boxShadow: `0 0 10px ${color}25`,
            }}
          >
            {verdict}
          </span>
        </div>

        <span className="mt-1 font-mono text-[7.5px] uppercase tracking-[0.24em] text-gunmetal-500 font-bold">
          SYSTEM RESILIENCE INDEX
        </span>
      </div>
    </div>
  );
}
