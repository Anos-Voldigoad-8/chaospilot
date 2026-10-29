"""Canonical host ports for the Phase 1 sample stack."""

from __future__ import annotations

GATEWAY_SERVICE = "gateway"
COLLECTOR_SERVICES: tuple[str, ...] = ("auth", "orders", "cache", "payments", "db")

SERVICE_PORTS: dict[str, int] = {
    "gateway": 8000,
    "auth": 8001,
    "orders": 8002,
    "cache": 8003,
    "payments": 8004,
    "db": 8005,
}

ALL_SERVICES: tuple[str, ...] = tuple(SERVICE_PORTS)


def service_url(service: str, host: str = "127.0.0.1") -> str:
    try:
        port = SERVICE_PORTS[service]
    except KeyError as exc:
        raise ValueError(f"unknown service: {service}") from exc
    return f"http://{host}:{port}"
