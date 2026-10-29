"""Convert database rows into API-friendly shapes."""

from __future__ import annotations

from typing import Any

from app.api.deps import service_status
from app.services.registry import SERVICES


def dependencies_of(row: dict[str, Any]) -> list[str]:
    raw = row.get("dependencies") or ""
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return [item for item in str(raw).split(",") if item]


def to_metric(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": float(row.get("timestamp", row.get("ts", 0.0))),
        "service_id": row["service_id"],
        "latency_ms": float(row.get("latency_ms", 0.0)),
        "error_rate": float(row.get("error_rate", 0.0)),
        "cpu_percent": float(row.get("cpu_percent", 0.0)),
        "memory_mb": float(row.get("memory_mb", 0.0)),
        "request_rate": float(row.get("request_rate", 0.0)),
    }


def to_service(row: dict[str, Any], latest: dict[str, Any] | None, faults: int) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "port": row["port"],
        "url": row["url"],
        "description": row.get("description", ""),
        "dependencies": dependencies_of(row),
        "status": service_status(latest, faults),
        "latest": to_metric(latest) if latest else None,
        "active_faults": faults,
    }


def service_port_map() -> dict[str, int]:
    return {service.id: service.port for service in SERVICES}
