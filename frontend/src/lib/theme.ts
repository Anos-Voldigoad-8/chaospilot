import type { ServiceStatus } from "../types/chaos";

export const COLORS = {
  cyan: "#20e7de",
  cyanDim: "rgba(32, 231, 222, 0.22)",
  mint: "#41f2a6",
  amber: "#ffb224",
  red: "#ff3d55",
  muted: "#5b7c85",
} as const;

export const STATUS_COLOR: Record<ServiceStatus, string> = {
  ok: COLORS.mint,
  warn: COLORS.amber,
  bad: COLORS.red,
};

export const STATUS_LABEL: Record<ServiceStatus, string> = {
  ok: "nominal",
  warn: "stress",
  bad: "failure",
};

export function scoreColor(score: number): string {
  if (score >= 80) return COLORS.mint;
  if (score >= 50) return COLORS.amber;
  return COLORS.red;
}

export function scoreVerdict(score: number): string {
  if (score >= 80) return "nominal";
  if (score >= 50) return "degraded";
  return "critical";
}
