"""Environment-driven settings for the Phase 3 API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from db import DEFAULT_DB_PATH


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


@dataclass(frozen=True)
class ApiSettings:
    """All non-secret configuration needed to run one experiment."""

    db_path: Path = DEFAULT_DB_PATH
    host: str = "127.0.0.1"
    baseline_seconds: float = 10.0
    fault_seconds: float = 20.0
    recovery_seconds: float = 10.0
    collector_interval: float = 1.0
    latency_ms: float = 2_000.0
    memory_mb: int = 256
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    stack_directory: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "sample-stack"
    )

    @classmethod
    def from_env(cls) -> ApiSettings:
        origins = os.getenv(
            "CHAOSPILOT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        )
        return cls(
            db_path=Path(os.getenv("CHAOSPILOT_DB_PATH", str(DEFAULT_DB_PATH))),
            host=os.getenv("SAMPLE_STACK_HOST", "127.0.0.1"),
            baseline_seconds=_env_float("CHAOSPILOT_BASELINE_SECONDS", 10.0),
            fault_seconds=_env_float("CHAOSPILOT_FAULT_SECONDS", 20.0),
            recovery_seconds=_env_float("CHAOSPILOT_RECOVERY_SECONDS", 10.0),
            collector_interval=_env_float("CHAOSPILOT_COLLECTOR_INTERVAL", 1.0),
            latency_ms=_env_float("CHAOSPILOT_LATENCY_MS", 2_000.0),
            memory_mb=_env_int("CHAOSPILOT_MEMORY_MB", 256),
            cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
        )
