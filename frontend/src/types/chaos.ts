export type ServiceStatus = "ok" | "warn" | "bad";
export type FaultKind = "kill" | "latency" | "memory";
export type DataSource = "live" | "cached" | "seed";
export type LogLevel = "info" | "warn" | "error" | "success";
export type ConnectionState = "connecting" | "live" | "offline" | "mock";

export interface TopologyNode {
  id: string;
  label: string;
  port: number;
  role: string;
  entry: boolean;
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
}

export interface Topology {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface StateEvent {
  type: "state";
  service: string;
  status: ServiceStatus;
  latency_ms: number;
}

export interface LogEvent {
  type: "log";
  level: LogLevel | "info" | "warn" | "error";
  text: string;
}

export interface MetricsEvent {
  type: "metrics";
  gateway_latency: number;
  error_rate: number;
}

export interface AnomalyEvent {
  type: "anomaly";
  value: number;
  services: Record<string, number>;
}

export interface ScoreEvent {
  type: "score";
  value: number;
  failed?: string[];
  degraded?: string[];
  contained?: boolean;
  bonus?: number;
}

export interface PostmortemStructured {
  root_cause: string;
  blast_radius: string;
  fixes: string[];
  word_count?: number;
}

export interface PostmortemEvent {
  type: "postmortem";
  text: string;
  source?: "llm" | "template";
  structured?: PostmortemStructured;
}

export type WsEvent =
  | StateEvent
  | LogEvent
  | MetricsEvent
  | AnomalyEvent
  | ScoreEvent
  | PostmortemEvent;

export interface AgentStatus {
  provider: string;
  model: string | null;
  mode: "llm" | "fallback";
}

export interface ScoreBreakdown {
  value: number;
  failed: string[];
  degraded: string[];
  contained: boolean;
  bonus: number;
}

export interface RunOutcome {
  id: number | null;
  fault: FaultKind;
  target: string;
  fixes: boolean;
  score: number;
  at: number;
}

export interface ServiceRuntime {
  status: ServiceStatus;
  latency_ms: number;
}

export interface LogLine {
  id: number;
  at: number;
  level: LogLevel;
  text: string;
}

export interface MetricSample {
  t: number;
  latency: number;
  errorRate: number;
}

export interface Scenario {
  id: number;
  fault_type: FaultKind;
  target_service: string;
  duration_minutes: number;
  severity: string;
  load_curve: Array<{ t: string; v: number }>;
  source: string;
  source_url: string;
  data_source: DataSource;
  title: string;
  created_at: number;
}

export interface ExperimentSummary {
  id: number;
  fault: string;
  target: string;
  fixes: boolean;
  status: string;
  score: number | null;
  started: number;
  ended: number | null;
  sample_count?: number;
  error_count?: number;
}

export interface ExperimentDetail extends ExperimentSummary {
  postmortem: string | null;
  resilient: boolean;
  error: string | null;
  phases?: Record<string, { samples: number; errors: number; p50_ms: number | null }>;
}

export interface RunRequest {
  scenario_id: number;
  fixes: boolean;
}
