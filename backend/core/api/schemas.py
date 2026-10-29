"""Pydantic schemas for the public API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MetricPoint(BaseModel):
    timestamp: float
    service_id: str
    latency_ms: float
    error_rate: float
    cpu_percent: float
    memory_mb: float
    request_rate: float


class ServiceOut(BaseModel):
    id: str
    name: str
    port: int
    url: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    status: Literal["healthy", "degraded", "down", "unknown"] = "unknown"
    latest: dict[str, Any] | None = None
    active_faults: int = 0


class AnomalyOut(BaseModel):
    id: int
    service_id: str
    metric: str
    value: float
    score: float
    severity: str
    detected_at: float
    details: dict[str, Any] = Field(default_factory=dict)


class FaultOut(BaseModel):
    id: str
    service_id: str
    fault_type: str
    parameters: dict[str, float] = Field(default_factory=dict)
    status: str
    started_at: float
    ends_at: float | None = None
    recovered_at: float | None = None
    engine: str | None = None


class IncidentOut(BaseModel):
    id: str
    service_id: str
    anomaly_id: int | None = None
    summary: str
    root_cause: str
    evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float
    provider: str
    created_at: float


class HealthOut(BaseModel):
    status: str
    version: str
    environment: str
    simulation_mode: bool
    docker_enabled: bool
    llm_provider: str


class OverviewSummary(BaseModel):
    services_total: int
    services_healthy: int
    services_degraded: int
    active_faults: int
    anomalies_recent: int
    incidents_recent: int


class OverviewOut(BaseModel):
    generated_at: float
    summary: OverviewSummary
    services: list[ServiceOut]
    latest_metrics: list[MetricPoint]
    anomalies: list[AnomalyOut]
    active_faults: list[FaultOut]
    incidents: list[IncidentOut]
    llm: dict[str, Any]


class MetricsResponse(BaseModel):
    service_id: str | None
    minutes: int
    points: list[MetricPoint]


class MetricSummary(BaseModel):
    service_id: str
    avg_latency_ms: float
    avg_error_rate: float
    avg_cpu_percent: float
    avg_memory_mb: float
    avg_request_rate: float
    samples: int


class TrainingResponse(BaseModel):
    trained: bool
    samples: int
    services: int
    model_path: str
    reason: str = ""


class DetectionResponse(BaseModel):
    detected: int
    anomalies: list[AnomalyOut]


class DiagnoseRequest(BaseModel):
    service_id: str
    anomaly_id: int | None = None
