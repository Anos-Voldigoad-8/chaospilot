"""Chaos fault definitions and validation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.services.registry import SERVICE_IDS


class FaultType(str, Enum):
    LATENCY = "latency"
    ERROR = "error"
    CRASH = "crash"
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"


DEFAULT_PARAMETERS: dict[FaultType, dict[str, float]] = {
    FaultType.LATENCY: {"latency_ms": 800.0},
    FaultType.ERROR: {"error_rate": 0.5},
    FaultType.CRASH: {},
    FaultType.CPU: {"cpu_percent": 90.0},
    FaultType.MEMORY: {"memory_mb": 512.0},
    FaultType.NETWORK: {"packet_loss": 1.0},
}

PARAMETER_BOUNDS: dict[str, tuple[float, float]] = {
    "latency_ms": (50.0, 60_000.0),
    "error_rate": (0.0, 1.0),
    "cpu_percent": (10.0, 100.0),
    "memory_mb": (64.0, 4096.0),
    "packet_loss": (0.0, 1.0),
}


class FaultRequest(BaseModel):
    service_id: str
    fault_type: FaultType
    duration_seconds: int = Field(default=60, ge=10, le=3600)
    parameters: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> FaultRequest:
        if self.service_id not in SERVICE_IDS:
            raise ValueError(f"unknown service: {self.service_id}")
        for name, value in self.normalized_parameters().items():
            low, high = PARAMETER_BOUNDS[name]
            if not low <= value <= high:
                raise ValueError(f"{name} must be between {low} and {high}")
        return self

    def normalized_parameters(self) -> dict[str, float]:
        values = dict(DEFAULT_PARAMETERS[self.fault_type])
        for name, value in self.parameters.items():
            if name in values:
                values[name] = float(value)
        return values

    def as_parameters(self) -> dict[str, Any]:
        return {name: float(value) for name, value in self.normalized_parameters().items()}
