"""Feature extraction shared by training and scoring."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

FEATURE_NAMES: tuple[str, ...] = (
    "latency_ms",
    "error_rate",
    "cpu_percent",
    "memory_mb",
    "request_rate",
)

# Human-friendly labels and rough units used in anomaly details.
FEATURE_LABELS: dict[str, str] = {
    "latency_ms": "latency (ms)",
    "error_rate": "error rate",
    "cpu_percent": "CPU (%)",
    "memory_mb": "memory (MB)",
    "request_rate": "request rate",
}


def row_to_vector(row: Mapping[str, Any]) -> list[float]:
    """Convert a metric row (or API payload) into a numeric feature vector."""
    vector: list[float] = []
    for name in FEATURE_NAMES:
        try:
            vector.append(float(row.get(name, 0.0) or 0.0))
        except (TypeError, ValueError):
            vector.append(0.0)
    return vector


def row_to_dict(row: Mapping[str, Any]) -> dict[str, float]:
    return dict(zip(FEATURE_NAMES, row_to_vector(row), strict=True))
