"""Shared FastAPI harness for the ChaosPilot sample stack.

Adds p50 latency tracking, chaos endpoints, dependency error handling and the
optional resilient dependency client to every service.
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

import psutil
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from common.http_client import (
    DEFAULT_TIMEOUT_SECONDS,
    RESILIENT_TIMEOUT_SECONDS,
    DependencyClient,
    DependencyError,
)

BYTES_PER_MB = 1024 * 1024
PAGE_SIZE = 4096
SERVICE_NAME = os.getenv("SERVICE_NAME", "service")
RESILIENT = os.getenv("RESILIENT", "false").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class ChaosState:
    """Faults currently applied to this process."""

    latency_ms: float = 0.0
    memory_blocks: list[bytearray] = field(default_factory=list)

    @property
    def memory_mb(self) -> float:
        return round(sum(len(block) for block in self.memory_blocks) / BYTES_PER_MB, 2)

    @property
    def active(self) -> bool:
        return self.latency_ms > 0 or bool(self.memory_blocks)

    def allocate(self, mb: int) -> None:
        if mb <= 0:
            return
        block = bytearray(mb * BYTES_PER_MB)
        # Touch one byte per page so the memory is actually resident, not lazy.
        for offset in range(0, len(block), PAGE_SIZE):
            block[offset] = 1
        self.memory_blocks.append(block)

    def reset(self) -> None:
        self.latency_ms = 0.0
        self.memory_blocks.clear()


@dataclass
class Telemetry:
    """Response-time samples and counters."""

    durations_ms: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    requests: int = 0
    errors: int = 0
    started_at: float = field(default_factory=time.time)

    def record(self, duration_ms: float, failed: bool) -> None:
        self.durations_ms.append(duration_ms)
        self.requests += 1
        if failed:
            self.errors += 1

    def p50_latency_ms(self) -> float:
        if not self.durations_ms:
            return 0.0
        return round(statistics.median(self.durations_ms), 3)

    @property
    def error_rate(self) -> float:
        return self.errors / self.requests if self.requests else 0.0


class LatencyPayload(BaseModel):
    ms: float = Field(ge=0, le=60_000)


class MemoryPayload(BaseModel):
    mb: int = Field(ge=0, le=1024)


def _service_metrics(name: str, telemetry: Telemetry, state: ChaosState) -> dict[str, Any]:
    process = psutil.Process()
    return {
        "service": name,
        "timestamp": time.time(),
        "latency_ms": telemetry.p50_latency_ms(),
        "error_rate": round(telemetry.error_rate, 4),
        "cpu_percent": round(process.cpu_percent(interval=None), 3),
        "memory_mb": round(process.memory_info().rss / BYTES_PER_MB, 3),
        "request_rate": telemetry.requests,
        "requests_sampled": len(telemetry.durations_ms),
        "fault_latency_ms": state.latency_ms,
        "memory_held_mb": state.memory_mb,
        "resilient": RESILIENT,
    }


def create_app(
    name: str,
    *,
    register_routes: Callable[[FastAPI], None] | None = None,
) -> FastAPI:
    app = FastAPI(title=f"ChaosPilot {name}", version="0.2.0")
    state = ChaosState()
    telemetry = Telemetry()
    client = DependencyClient(name, RESILIENT)

    app.state.chaos = state
    app.state.telemetry = telemetry
    app.state.dependency_client = client
    app.state.resilient = RESILIENT

    @app.exception_handler(DependencyError)
    async def dependency_error_handler(
        request: Request, exc: DependencyError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={
                "status": "dependency_error",
                "service": name,
                "dependency": exc.dependency,
                "detail": exc.detail,
                "resilient": RESILIENT,
            },
        )

    @app.middleware("http")
    async def chaos_middleware(request: Request, call_next: Any) -> Response:
        started = time.perf_counter()
        if state.latency_ms > 0:
            await asyncio.sleep(state.latency_ms / 1000.0)
        try:
            response = await call_next(request)
        except Exception:
            telemetry.record((time.perf_counter() - started) * 1000.0, True)
            raise
        telemetry.record(
            (time.perf_counter() - started) * 1000.0,
            response.status_code >= 500,
        )
        return response

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "degraded" if state.active else "ok",
            "service": name,
            "p50_latency_ms": telemetry.p50_latency_ms(),
            "sampled_requests": len(telemetry.durations_ms),
            "uptime_seconds": round(time.time() - telemetry.started_at, 2),
            "resilient": RESILIENT,
            "http_timeout_seconds": (
                RESILIENT_TIMEOUT_SECONDS if RESILIENT else DEFAULT_TIMEOUT_SECONDS
            ),
            "retries": 1 if RESILIENT else 0,
            "circuit_breaker": RESILIENT,
            "fault_latency_ms": state.latency_ms,
            "memory_held_mb": state.memory_mb,
        }

    @app.get("/metrics")
    async def metrics() -> dict[str, Any]:
        return _service_metrics(name, telemetry, state)

    @app.post("/_chaos/latency")
    async def apply_latency(payload: LatencyPayload) -> dict[str, Any]:
        state.latency_ms = payload.ms
        return {"service": name, "latency_ms": state.latency_ms}

    @app.post("/_chaos/memory")
    async def apply_memory(payload: MemoryPayload) -> dict[str, Any]:
        await asyncio.to_thread(state.allocate, payload.mb)
        return {
            "service": name,
            "allocated_mb": payload.mb,
            "memory_held_mb": state.memory_mb,
        }

    @app.post("/_chaos/reset")
    async def reset_chaos() -> dict[str, Any]:
        state.reset()
        return {"service": name, "status": "reset", "memory_held_mb": state.memory_mb}

    if register_routes is not None:
        register_routes(app)

    return app
