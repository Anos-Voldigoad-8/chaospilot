import type {
  Anomaly,
  Fault,
  FaultPayload,
  Health,
  Incident,
  MetricsResponse,
  Overview,
} from "../types/api";

// Only public configuration from import.meta.env is read here. No secrets.
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
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string | unknown };
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Keep the generic message when the body is not JSON.
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/health"),
  overview: () => request<Overview>("/api/overview"),
  metrics: (serviceId: string, minutes = 15) =>
    request<MetricsResponse>(
      `/api/metrics?service_id=${encodeURIComponent(serviceId)}&minutes=${minutes}`,
    ),
  anomalies: (limit = 50) => request<Anomaly[]>(`/api/anomalies?limit=${limit}`),
  train: () =>
    request<{ trained: boolean; samples: number; services: number }>(
      "/api/anomalies/train",
      { method: "POST" },
    ),
  detect: () =>
    request<{ detected: number; anomalies: Anomaly[] }>("/api/anomalies/detect", {
      method: "POST",
    }),
  faults: () => request<Fault[]>("/api/faults"),
  injectFault: (payload: FaultPayload) =>
    request<Fault>("/api/faults", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  recoverFault: (faultId: string) =>
    request<Fault>(`/api/faults/${encodeURIComponent(faultId)}/recover`, {
      method: "POST",
    }),
  diagnose: (serviceId: string, anomalyId?: number) =>
    request<Incident>("/api/agent/diagnose", {
      method: "POST",
      body: JSON.stringify({
        service_id: serviceId,
        anomaly_id: anomalyId ?? null,
      }),
    }),
  incidents: () => request<Incident[]>("/api/incidents?limit=20"),
};
