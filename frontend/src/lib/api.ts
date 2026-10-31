import type {
  AgentPlan,
  AgentStatus,
  ExperimentDetail,
  ExperimentSummary,
  RunRequest,
  Topology,
} from "../types/chaos";

// Public, non-secret configuration only. The Vite dev proxy forwards /api,
// /topology, /experiments, /agent and /ws to the backend, so an empty base
// means "same origin" and keeps the browser free of hardcoded ports.
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
  agentPlan: () =>
    request<AgentPlan>("/agent/plan", {
      method: "POST",
    }),
  agentStatus: () => request<AgentStatus>("/agent/status"),
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
