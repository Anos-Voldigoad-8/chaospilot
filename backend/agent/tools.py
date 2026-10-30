"""Agent tools over the sample stack and stored telemetry.

The functions are deliberately small and synchronous so an LLM or a test can
call them directly. Async callers should wrap them in ``asyncio.to_thread``.
"""

from __future__ import annotations

import time
from typing import Any

from chaos.engine import ChaosEngine
from db import ChaosDatabase
from service_map import ALL_SERVICES, SERVICE_PORTS
from topology import topology


def get_topology() -> dict[str, Any]:
    """Return the sample-stack nodes and directed dependency edges."""
    return topology()


def inject_fault(
    service: str,
    type: str,
    value: float | int | None = None,
    *,
    engine: ChaosEngine | None = None,
) -> dict[str, Any]:
    """Inject one fault and return the chaos-engine result.

    ``kill`` ignores ``value``; ``latency`` uses milliseconds (default 2000);
    ``memory`` uses megabytes (default 256).
    """
    if service not in SERVICE_PORTS:
        return {"ok": False, "action": type, "service": service, "error": "unknown service"}
    chaos = engine or ChaosEngine()
    if type == "kill":
        return chaos.kill(service)
    if type == "latency":
        return chaos.latency(service, float(value if value is not None else 2_000.0))
    if type == "memory":
        return chaos.memory(service, int(value if value is not None else 256))
    return {
        "ok": False,
        "action": type,
        "service": service,
        "error": f"unsupported fault: {type}",
    }


def read_metrics(
    service: str,
    database: ChaosDatabase | None = None,
    *,
    window_seconds: float = 60.0,
) -> dict[str, Any]:
    """Summarise the recent telemetry of one service."""
    store = database or ChaosDatabase()
    now = time.time()
    rows = store.samples_between(now - window_seconds, now + 1.0, service=service)
    latencies = [
        float(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None
    ]
    latest = rows[-1] if rows else None
    return {
        "service": service,
        "window_seconds": window_seconds,
        "samples": len(rows),
        "latency_mean": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        "latency_max": round(max(latencies), 1) if latencies else 0.0,
        "error_rate": round(
            sum(1 for row in rows if row.get("error")) / len(rows), 4
        )
        if rows
        else 0.0,
        "up_ratio": round(sum(1 for row in rows if row.get("up")) / len(rows), 4)
        if rows
        else 0.0,
        "latest": {
            "ts": latest.get("ts"),
            "up": bool(latest.get("up")),
            "latency_ms": latest.get("latency_ms"),
            "error": bool(latest.get("error")),
        }
        if latest
        else None,
    }


def read_logs(
    service: str,
    database: ChaosDatabase | None = None,
    *,
    window_seconds: float = 120.0,
    limit: int = 40,
) -> dict[str, Any]:
    """Return recent abnormal telemetry lines for one service.

    The sample stack does not ship a log shipper, so lines are derived from the
    collector samples (failed probes and latency spikes). That is the same
    evidence the dashboard shows, without inventing container logs.
    """
    store = database or ChaosDatabase()
    now = time.time()
    rows = store.samples_between(now - window_seconds, now + 1.0, service=service)
    lines: list[dict[str, Any]] = []
    for row in rows:
        timestamp = round(float(row["ts"]), 3)
        latency = row.get("latency_ms")
        if row.get("error") or not row.get("up"):
            lines.append(
                {
                    "at": timestamp,
                    "level": "error",
                    "message": f"{service} probe failed (up={bool(row.get('up'))})",
                }
            )
        elif latency is not None and float(latency) > 1_000.0:
            lines.append(
                {
                    "at": timestamp,
                    "level": "warn",
                    "message": f"{service} latency spike: {float(latency):.0f}ms",
                }
            )

    if not lines:
        latest = rows[-1] if rows else None
        lines.append(
            {
                "at": round(float(latest["ts"]), 3) if latest else round(now, 3),
                "level": "info",
                "message": f"no failures or latency spikes for {service} "
                f"in the last {window_seconds:.0f}s",
            }
        )
    return {
        "service": service,
        "window_seconds": window_seconds,
        "lines": lines[-limit:],
        "count": len(lines),
    }


def rollback(*, engine: ChaosEngine | None = None) -> dict[str, Any]:
    """Clear HTTP faults and restore every service container."""
    chaos = engine or ChaosEngine()
    reset = chaos.reset_all()
    restored = {service: chaos.restore(service) for service in ALL_SERVICES}
    ok = bool(reset.get("ok")) and all(
        bool(result.get("ok")) for result in restored.values()
    )
    return {"action": "rollback", "ok": ok, "reset": reset, "restored": restored}
