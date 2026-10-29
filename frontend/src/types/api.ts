export type ServiceStatus = "healthy" | "degraded" | "down" | "unknown";
export type Severity = "low" | "medium" | "high" | "critical";

export interface MetricPoint {
  timestamp: number;
  service_id: string;
  latency_ms: number;
  error_rate: number;
  cpu_percent: number;
  memory_mb: number;
  request_rate: number;
}

export interface Service {
  id: string;
  name: string;
  port: number;
  url: string;
  description: string;
  dependencies: string[];
  status: ServiceStatus;
  latest: MetricPoint | null;
  active_faults: number;
}

export interface Anomaly {
  id: number;
  service_id: string;
  metric: string;
  value: number;
  score: number;
  severity: Severity;
  detected_at: number;
  details: {
    top_feature?: string;
    deviations?: Record<string, number>;
    model_flagged?: boolean;
    explanation?: string;
  };
}

export interface Fault {
  id: string;
  service_id: string;
  fault_type: string;
  parameters: Record<string, number>;
  status: string;
  started_at: number;
  ends_at: number | null;
  recovered_at: number | null;
  engine?: string | null;
}

export interface Incident {
  id: string;
  service_id: string;
  anomaly_id: number | null;
  summary: string;
  root_cause: string;
  evidence: string[];
  recommendations: string[];
  confidence: number;
  provider: string;
  created_at: number;
}

export interface OverviewSummary {
  services_total: number;
  services_healthy: number;
  services_degraded: number;
  active_faults: number;
  anomalies_recent: number;
  incidents_recent: number;
}

export interface LLMStatus {
  provider: string;
  model: string;
  client_configured: boolean;
  mode: string;
  timeout_seconds: number;
}

export interface Overview {
  generated_at: number;
  summary: OverviewSummary;
  services: Service[];
  latest_metrics: MetricPoint[];
  anomalies: Anomaly[];
  active_faults: Fault[];
  incidents: Incident[];
  llm: LLMStatus;
}

export interface MetricsResponse {
  service_id: string | null;
  minutes: number;
  points: MetricPoint[];
}

export interface Health {
  status: string;
  version: string;
  environment: string;
  simulation_mode: boolean;
  docker_enabled: boolean;
  llm_provider: string;
}

export type FaultType = "latency" | "error" | "crash" | "cpu" | "memory" | "network";

export interface FaultPayload {
  service_id: string;
  fault_type: FaultType;
  duration_seconds: number;
  parameters: Record<string, number>;
}
