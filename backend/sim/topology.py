"""In-process simulator topology: services, dependencies and baseline config.

The simulated stack has six services with the same dependency graph as the old
Docker sample stack:

    gateway -> auth, gateway -> orders
    auth -> cache
    orders -> payments, orders -> db
    payments -> db

Every service declares a baseline latency (ms), a baseline error rate and a
load capacity (requests per second). A fault on one service raises latency and
errors for itself and every caller upstream of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: caller -> (callee, ...)
DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("gateway", "auth"),
    ("gateway", "orders"),
    ("auth", "cache"),
    ("orders", "payments"),
    ("orders", "db"),
    ("payments", "db"),
)

ALL_SERVICES: tuple[str, ...] = (
    "gateway",
    "auth",
    "orders",
    "payments",
    "cache",
    "db",
)


@dataclass(frozen=True)
class ServiceConfig:
    """Static configuration for one simulated service."""

    name: str
    baseline_latency_ms: float
    baseline_error_rate: float
    load_capacity_rps: float
    role: str


SERVICE_CONFIGS: dict[str, ServiceConfig] = {
    "gateway": ServiceConfig(
        name="gateway",
        baseline_latency_ms=60.0,
        baseline_error_rate=0.005,
        load_capacity_rps=1000.0,
        role="public entry point",
    ),
    "auth": ServiceConfig(
        name="auth",
        baseline_latency_ms=10.0,
        baseline_error_rate=0.002,
        load_capacity_rps=800.0,
        role="session verification",
    ),
    "orders": ServiceConfig(
        name="orders",
        baseline_latency_ms=15.0,
        baseline_error_rate=0.003,
        load_capacity_rps=900.0,
        role="order orchestration",
    ),
    "payments": ServiceConfig(
        name="payments",
        baseline_latency_ms=80.0,
        baseline_error_rate=0.004,
        load_capacity_rps=500.0,
        role="payment charges",
    ),
    "cache": ServiceConfig(
        name="cache",
        baseline_latency_ms=3.0,
        baseline_error_rate=0.001,
        load_capacity_rps=2000.0,
        role="in-memory session cache",
    ),
    "db": ServiceConfig(
        name="db",
        baseline_latency_ms=5.0,
        baseline_error_rate=0.001,
        load_capacity_rps=1500.0,
        role="in-memory database",
    ),
}

#: Direct callers of each service (reverse of DEPENDENCIES).
CALLERS_BY_SERVICE: dict[str, tuple[str, ...]] = {
    target: tuple(source for source, dependency in DEPENDENCIES if dependency == target)
    for target in {edge[1] for edge in DEPENDENCIES}
}


def affected_services(target: str, resilient: bool = False) -> frozenset[str]:
    """Services degraded by a fault on ``target``.

    With ``resilient=True`` the blast radius is contained to one hop: only the
    target and its direct callers are affected, not transitive upstream
    callers.
    """
    affected = {target}
    if not resilient:
        frontier = [target]
        while frontier:
            service = frontier.pop()
            for caller in CALLERS_BY_SERVICE.get(service, ()):
                if caller not in affected:
                    affected.add(caller)
                    frontier.append(caller)
    else:
        # One hop only: target plus direct callers.
        for caller in CALLERS_BY_SERVICE.get(target, ()):
            affected.add(caller)
    return frozenset(affected)


def topology() -> dict[str, Any]:
    """Return nodes and directed dependency edges for the dashboard."""
    nodes = [
        {
            "id": service,
            "label": service,
            "role": config.role,
            "baseline_latency_ms": config.baseline_latency_ms,
            "baseline_error_rate": config.baseline_error_rate,
            "load_capacity_rps": config.load_capacity_rps,
            "entry": service == "gateway",
        }
        for service, config in SERVICE_CONFIGS.items()
    ]
    edges = [
        {"id": f"{source}->{target}", "source": source, "target": target}
        for source, target in DEPENDENCIES
    ]
    return {"nodes": nodes, "edges": edges}
