"""Synthetic telemetry used when Docker/the sample stack is unavailable.

The simulator is also responsible for seeding a short healthy history at
startup so the ML model can train and the dashboard is populated immediately.
"""

from __future__ import annotations

import random
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.database import Database
from core.services import store
from core.services.registry import SERVICES


@dataclass(frozen=True)
class ServiceProfile:
    latency_ms: float
    error_rate: float
    cpu_percent: float
    memory_mb: float
    request_rate: float


PROFILES: dict[str, ServiceProfile] = {
    "catalog": ServiceProfile(24.0, 0.002, 12.0, 140.0, 55.0),
    "cart": ServiceProfile(31.0, 0.003, 18.0, 155.0, 42.0),
    "checkout": ServiceProfile(48.0, 0.004, 22.0, 180.0, 30.0),
    "payments": ServiceProfile(60.0, 0.005, 25.0, 190.0, 28.0),
    "notifications": ServiceProfile(18.0, 0.001, 8.0, 120.0, 20.0),
}

DEFAULT_PROFILE = ServiceProfile(35.0, 0.003, 15.0, 150.0, 30.0)
DEPENDENCY_PROPAGATION = 0.35


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _jitter(value: float, ratio: float = 0.08) -> float:
    return value * (1.0 + random.uniform(-ratio, ratio))


def _apply_fault(
    sample: dict[str, float], fault_type: str, parameters: Mapping[str, Any]
) -> None:
    if fault_type == "latency":
        sample["latency_ms"] += float(parameters.get("latency_ms", 800.0))
        sample["request_rate"] *= 0.8
    elif fault_type == "error":
        sample["error_rate"] += float(parameters.get("error_rate", 0.5))
        sample["request_rate"] *= 0.7
    elif fault_type == "crash":
        sample["error_rate"] = 1.0
        sample["request_rate"] = 0.0
        sample["latency_ms"] = 0.0
    elif fault_type == "cpu":
        overhead = float(parameters.get("cpu_percent", 90.0))
        sample["cpu_percent"] += overhead
        sample["latency_ms"] *= 1.0 + overhead / 100.0
    elif fault_type == "memory":
        sample["memory_mb"] += float(parameters.get("memory_mb", 512.0))
        sample["latency_ms"] *= 1.1
    elif fault_type == "network":
        loss = float(parameters.get("packet_loss", 1.0))
        sample["error_rate"] += 0.5 * loss
        sample["latency_ms"] *= 1.0 + loss
    sample["error_rate"] = _clamp(sample["error_rate"], 0.0, 1.0)
    sample["cpu_percent"] = _clamp(sample["cpu_percent"], 0.0, 100.0)


def generate_sample(
    service_id: str,
    active_faults: Sequence[Mapping[str, Any]] = (),
    dependency_faults: Sequence[Mapping[str, Any]] = (),
    *,
    timestamp: float | None = None,
) -> dict[str, Any]:
    """Create one plausible metric sample for a service."""
    profile = PROFILES.get(service_id, DEFAULT_PROFILE)
    sample: dict[str, float] = {
        "timestamp": timestamp or time.time(),
        "latency_ms":_jitter(profile.latency_ms),
        "error_rate": _clamp(_jitter(profile.error_rate, 0.4), 0.0, 1.0),
        "cpu_percent": _jitter(profile.cpu_percent, 0.15),
        "memory_mb": _jitter(profile.memory_mb, 0.05),
        "request_rate": _jitter(profile.request_rate, 0.12),
    }

    for fault in active_faults:
        _apply_fault(
            sample,
            str(fault.get("fault_type", "")),
            fault.get("parameters") or {},
        )

    # A broken dependency drags the caller down, partially.
    for fault in dependency_faults:
        propagated = dict(sample)
        _apply_fault(
            propagated,
            str(fault.get("fault_type", "")),
            fault.get("parameters") or {},
        )
        for key in ("latency_ms", "error_rate", "cpu_percent", "memory_mb"):
            sample[key] += (propagated[key] - sample[key]) * DEPENDENCY_PROPAGATION
        sample["request_rate"] += (
            propagated["request_rate"] - sample["request_rate"]
        ) * DEPENDENCY_PROPAGATION

    sample["timestamp"] = timestamp or time.time()
    for key in ("latency_ms", "cpu_percent", "memory_mb", "request_rate"):
        sample[key] = round(max(0.0, sample[key]), 3)
    sample["error_rate"] = round(_clamp(sample["error_rate"], 0.0, 1.0), 4)
    return sample


def seed_history(database: Database, *, points_per_service: int = 120, interval: float = 5.0) -> int:
    """Backfill a healthy history once so the model can train immediately."""
    if store.metric_count(database) > 0:
        return 0
    now = time.time()
    written = 0
    for service in SERVICES:
        for index in range(points_per_service, 0, -1):
            timestamp = now - index * interval
            store.record_metric(
                database,
                service.id,
                generate_sample(service.id, timestamp=timestamp),
            )
            written += 1
    return written
