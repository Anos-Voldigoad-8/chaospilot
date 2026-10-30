export type ServiceStatus = "ok" | "warn" | "bad";
export type FaultKind = "kill" | "latency" | "memory";
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

export interface ScoreEvent {
  type: "score";
  value: number;
}

export interface PostmortemEvent {
  type: "postmortem";
  text: string;
}

export type WsEvent = StateEvent | LogEvent | MetricsEvent | ScoreEvent | PostmortemEvent;

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
  fault: FaultKind;
  target: string;
  fixes: boolean;
}
