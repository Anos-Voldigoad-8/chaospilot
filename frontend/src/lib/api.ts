import type {
  AgentStatus,
  ExperimentDetail,
  ExperimentSummary,
  RunRequest,
  Scenario,
  Topology,
} from "../types/chaos";

// Public, non-secret configuration only. When deployed on Vercel, the /api/*
// route is rewritten to the backend service. In local dev, Vite proxies /api.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    // fetch only rejects for network/CORS failures, never for HTTP errors.
    throw new ApiError(
      `backend unreachable at ${API_BASE || window.location.origin}`,
      0,
    );
  }

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
  health: () => request<{ status: string }>("/health"),
  topology: () => request<Topology>("/topology"),
  agentStatus: () => request<AgentStatus>("/agent/status"),
  // Collect real-world data via the backend data agent. Streams progress over
  // the WebSocket; returns the scenarios it persisted.
  agentCollect: () =>
    request<{ scenarios: Scenario[]; count: number }>("/agent/collect", {
      method: "POST",
    }),
  scenarios: (limit = 50) =>
    request<{ scenarios: Scenario[]; count: number }>(
      `/scenarios?limit=${limit}`,
    ),
  // An experiment can ONLY run a scenario stored by the agent.
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
  // Mark the fault of a running experiment as fixed so it transitions from the
  // paused broken state into recovery (APPLY FIX & RECOVER).
  resolveExperiment: (id: number) =>
    request<{ id: number; status: string; fault_ended: number }>(
      `/experiments/${id}/resolve`,
      { method: "POST" },
    ),
  // Stop the active experiment so a new one can be started (STOP / RESET).
  stopExperiment: (id?: number | null) =>
    request<{ id: number; status: string; fault_ended: number }>(
      id ? `/experiments/${id}/stop` : `/experiments/stop`,
      { method: "POST" },
    ),
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
