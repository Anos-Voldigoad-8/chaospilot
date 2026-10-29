"""Static topology of the Phase 1 sample stack.

The dashboard renders these nodes and edges directly; ``GET /topology`` returns
the same data. Node ids match the collector and chaos-engine service names.
"""

from __future__ import annotations

from typing import Any

from service_map import SERVICE_PORTS

NODE_ROLES: dict[str, str] = {
    "gateway": "entry point",
    "auth": "session verification",
    "orders": "order orchestration",
    "cache": "in-memory cache",
    "payments": "payment charges",
    "db": "in-memory database",
}

DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("gateway", "auth"),
    ("gateway", "orders"),
    ("auth", "cache"),
    ("orders", "payments"),
    ("orders", "db"),
    ("payments", "db"),
)


def topology() -> dict[str, Any]:
    """Return nodes (with host ports) and directed dependency edges."""
    nodes = [
        {
            "id": service,
            "label": service,
            "port": port,
            "role": NODE_ROLES[service],
            "entry": service == "gateway",
        }
        for service, port in SERVICE_PORTS.items()
    ]
    edges = [
        {"id": f"{source}->{target}", "source": source, "target": target}
        for source, target in DEPENDENCIES
    ]
    return {"nodes": nodes, "edges": edges}
