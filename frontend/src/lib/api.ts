import type {
  ExperimentDetail,
  ExperimentSummary,
  RunRequest,
  Topology,
} from "../types/chaos";

// Public, non-secret configuration only. The Vite dev proxy forwards /api,
// /topology, /experiments and /ws to the backend, so an empty base means
// "same origin" and keeps the browser free of hardcoded ports.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Non-JSON error bodies keep the status message.
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export const api = {
  topology: () => request<Topology>("/topology"),
  runExperiment: (payload: RunRequest) =>
    request<ExperimentSummary>("/experiments/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  experiments: (limit = 12) =>
    request<{ experiments: ExperimentSummary[]; count: number }>(
      `/experiments?limit=${limit}`,
    ),
  experiment: (id: number) => request<ExperimentDetail>(`/experiments/${id}`),
};

/**
 * WebSocket location resolution, most specific first:
 *   1. `?ws=ws://host:port/ws` (handy while debugging a remote backend)
 *   2. `VITE_WS_URL`
 *   3. same-origin `/ws`, proxied to the backend by Vite in dev
 */
export function resolveWsUrl(): string {
  const override = new URLSearchParams(window.location.search).get("ws");
  if (override) return override;
  const configured = import.meta.env.VITE_WS_URL;
  if (configured) return configured;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws`;
}
