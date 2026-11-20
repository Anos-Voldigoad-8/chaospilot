import type { ServiceStatus } from "../types/chaos";

export const COLORS = {
  // Primary (60%): Cool Titanium Silk
  titanium: "#F1F3F6",
  titaniumBase: "#F1F3F6",
  titaniumHighlight: "#F8F9FB",
  titaniumFold: "#E8EBF1",
  titaniumShadow: "#DDE1EA",
  titaniumSurface: "#FFFFFF",
  titaniumBorder: "#DDE1EA",

  // Secondary (30%): Deep Gunmetal
  gunmetal: "#1E222B",
  gunmetalHover: "#2B303B",
  gunmetalRaised: "#2B303B",
  gunmetalMuted: "#5B6272",
  gunmetalDark: "#12151B",

  // Accent (10%): Soft Ultraviolet
  ultraviolet: "#6366F1",
  ultravioletDeep: "#7C3AED",
  ultravioletBright: "#818CF8",
  ultravioletGlow: "rgba(99, 102, 241, 0.14)", // Requested glow tint
  ultravioletDim: "rgba(99, 102, 241, 0.14)",

  // Legacy bridge
  pine: "#F1F3F6",
  moss: "#1E222B",
  celadon: "#6366F1",
  celadonBright: "#818CF8",
  celadonDim: "rgba(99, 102, 241, 0.14)",
  cyan: "#6366F1",
  cyanDim: "rgba(99, 102, 241, 0.14)",
  mint: "#10B981",
  amber: "#F59E0B",
  red: "#EF4444",
  muted: "#5B6272",
  ice: "#F8F9FB",
} as const;

export const STATUS_COLOR: Record<ServiceStatus, string> = {
  ok: "#10B981",
  warn: "#EF4444", // Strict Red signal (not yellow)
  bad: "#EF4444",
};

export const STATUS_LABEL: Record<ServiceStatus, string> = {
  ok: "nominal",
  warn: "stress",
  bad: "failure",
};

export function scoreColor(score: number): string {
  if (score >= 80) return "#6366F1";
  return "#EF4444"; // Red for any degraded or critical score (not yellow)
}

export function scoreVerdict(score: number): string {
  if (score >= 80) return "nominal";
  if (score >= 50) return "degraded";
  return "critical";
}
