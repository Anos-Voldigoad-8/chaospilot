"""Shared FastAPI service harness used by all five demo services.

Each service only defines its domain routes; this module supplies health,
metrics, fault injection and the chaos middleware so telemetry behaves
consistently across the stack.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import psutil
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

SERVICE_NAME = os.getenv("SERVICE_NAME", "service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")


@dataclass
class FaultState:
    """Fault knobs controlled by the ChaosPilot backend."""

    latency_ms: float = 0.0
    error_rate: float = 0.0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0

    def reset(self) -> None:
        self.latency_ms = 0.0
        self.error_rate = 0.0
        self.cpu_percent = 0.0
        self.memory_mb = 0.0

    @property
    def active(self) -> bool:
        return any(
            value > 0
            for value in (
                self.latency_ms,
                self.error_rate,
                self.cpu_percent,
                self.memory_mb,
            )
        )


@dataclass
class MetricsState:
    """Cheap in-process counters exposed on /metrics."""

    requests: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    started_at: float = field(default_factory=time.time)

    def record(self, latency_ms: float, failed: bool) -> None:
        self.requests += 1
        self.total_latency_ms += latency_ms
        if failed:
            self.errors += 1

    @property
    def error_rate(self) -> float:
        return self.errors / self.requests if self.requests else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.requests if self.requests else 0.0


class FaultRequest(BaseModel):
    latency_ms: float = Field(default=0.0, ge=0.0, le=60_000.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    cpu_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_mb: float = Field(default=0.0, ge=0.0, le=4096.0)


class ServiceInfo(BaseModel):
    name: str
    version: str
    status: str
    uptime_seconds: float
    fault_active: bool


def _current_usage(state: FaultState) -> tuple[float, float]:
    process = psutil.Process()
    cpu = process.cpu_percent(interval=None) + state.cpu_percent
    memory = process.memory_info().rss / (1024 * 1024) + state.memory_mb
    return min(cpu, 100.0), memory


def _should_fail(path: str, state: FaultState) -> bool:
    if path.startswith("/admin") or path in {"/health", "/metrics"}:
        return False
    return state.error_rate > 0 and random.random() < state.error_rate


def create_app(
    name: str,
    *,
    routes: Callable[[FastAPI], None] | None = None,
) -> FastAPI:
    """Build a service app with shared observability and chaos hooks."""

    app = FastAPI(title=f"ChaosPilot {name}", version=SERVICE_VERSION)
    state = FaultState()
    metrics = MetricsState()
    started_at = time.time()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.fault = state
    app.state.metrics = metrics
    app.state.service_name = name

    @app.middleware("http")
    async def chaos_middleware(request: Request, call_next: Any) -> Response:
        begin = time.perf_counter()
        path = request.url.path

        if state.latency_ms > 0:
            await asyncio.sleep(state.latency_ms / 1000.0)
        if _should_fail(path, state):
            elapsed_ms = (time.perf_counter() - begin) * 1000.0
            metrics.record(elapsed_ms, failed=True)
            return JSONResponse(
                status_code=503,
                content={"detail": "injected fault", "service": name},
            )

        try:
            response = await call_next(request)
        except Exception:  # pragma: no cover - defensive middleware
            metrics.record((time.perf_counter() - begin) * 1000.0, True)
            raise

        if not path.startswith("/admin"):
            metrics.record(
                (time.perf_counter() - begin) * 1000.0,
                failed=response.status_code >= 500,
            )
        return response

    @app.get("/", response_model=ServiceInfo)
    async def root() -> ServiceInfo:
        return ServiceInfo(
            name=name,
            version=SERVICE_VERSION,
            status="degraded" if state.active else "ok",
            uptime_seconds=round(time.time() - started_at, 2),
            fault_active=state.active,
        )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "degraded" if state.active else "ok",
            "service": name,
            "version": SERVICE_VERSION,
            "uptime_seconds": round(time.time() - started_at, 2),
            "fault_active": state.active,
        }

    @app.get("/metrics")
    async def service_metrics() -> dict[str, Any]:
        cpu, memory = _current_usage(state)
        return {
            "service": name,
            "timestamp": time.time(),
            "latency_ms": round(metrics.avg_latency_ms, 3),
            "error_rate": round(metrics.error_rate, 4),
            "cpu_percent": round(cpu, 3),
            "memory_mb": round(memory, 3),
            "request_rate": metrics.requests,
            "requests": metrics.requests,
            "errors": metrics.errors,
            "fault": {
                "latency_ms": state.latency_ms,
                "error_rate": state.error_rate,
                "cpu_percent": state.cpu_percent,
                "memory_mb": state.memory_mb,
            },
        }

    @app.get("/admin/state")
    async def admin_state() -> dict[str, Any]:
        return {
            "latency_ms": state.latency_ms,
            "error_rate": state.error_rate,
            "cpu_percent": state.cpu_percent,
            "memory_mb": state.memory_mb,
        }

    @app.post("/admin/fault")
    async def admin_fault(payload: FaultRequest) -> dict[str, Any]:
        state.latency_ms = payload.latency_ms
        state.error_rate = payload.error_rate
        state.cpu_percent = payload.cpu_percent
        state.memory_mb = payload.memory_mb
        return {"service": name, "status": "fault-applied", "fault": payload.model_dump()}

    @app.post("/admin/reset")
    async def admin_reset() -> dict[str, str]:
        state.reset()
        return {"service": name, "status": "reset"}

    if routes is not None:
        routes(app)

    return app
