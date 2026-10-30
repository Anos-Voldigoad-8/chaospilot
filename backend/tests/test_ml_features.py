"""Tests for the Phase 5 sliding-window feature builder."""

from __future__ import annotations

import math
from typing import Any

from ml.features import (
    FEATURE_NAMES,
    affected_services,
    build_windows,
)


def _row(
    ts: float,
    service: str,
    *,
    latency: float,
    label: int,
    experiment_id: int,
    up: bool = True,
    error: bool = False,
) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "ts": ts,
        "service": service,
        "up": up,
        "latency_ms": latency,
        "error": error,
        "label": label,
    }


def _series(
    service: str,
    *,
    baseline: float,
    fault: float,
    experiment_id: int = 1,
) -> list[dict[str, Any]]:
    rows = []
    for offset in range(10):
        ts = 100.0 + offset
        active = ts >= 102
        rows.append(
            _row(
                ts,
                service,
                latency=fault if active else baseline,
                label=1 if active else 0,
                experiment_id=experiment_id,
            )
        )
    return rows


def test_affected_services_follows_reverse_call_path() -> None:
    assert affected_services("db") == {"db", "payments", "orders", "gateway"}
    assert affected_services("gateway") == {"gateway"}
    assert affected_services("auth") == {"auth", "gateway"}


def test_windows_have_fixed_features_and_service_level_labels() -> None:
    runs = {
        1: {
            "id": 1,
            "fault": "latency",
            "target": "payments",
            "baseline_end": 102.0,
            "fault_started": 102.0,
            "fault_ended": 107.0,
            "recovery_end": 109.0,
        }
    }
    samples = []
    samples += _series("payments", baseline=8.0, fault=2_100.0)
    samples += _series("orders", baseline=14.0, fault=1_150.0)
    samples += _series("db", baseline=6.0, fault=6.0)
    samples += _series("auth", baseline=11.0, fault=11.0)

    windows = build_windows(samples, runs, window_seconds=5.0, min_samples=3)
    assert windows

    for window in windows:
        assert set(window.features) == set(FEATURE_NAMES)
        assert all(math.isfinite(value) for value in window.vector())
        assert len(window.vector()) == len(FEATURE_NAMES)

    payments = [
        window
        for window in windows
        if window.service == "payments" and window.end == 106.0
    ]
    assert payments and payments[0].label == 1
    assert payments[0].phase == "fault"
    assert payments[0].features["latency_mean"] > 1_000
    assert payments[0].features["dep_up_ratio"] == 1.0

    auth = [
        window for window in windows if window.service == "auth" and window.end == 106.0
    ]
    assert auth and auth[0].label == 0
    assert auth[0].phase == "fault-unaffected"

    assert not any(window.end == 108.0 for window in windows), "recovery is ambiguous"


def test_missing_dependency_data_is_neutral() -> None:
    runs = {
        1: {
            "id": 1,
            "fault": "kill",
            "target": "db",
            "fault_started": 102.0,
            "fault_ended": 105.0,
            "recovery_end": 107.0,
        }
    }
    samples = _series("gateway", baseline=60.0, fault=1_800.0)
    windows = build_windows(samples, runs)
    gateway = [window for window in windows if window.end == 104.0][0]
    assert gateway.features["dep_up_ratio"] == 1.0
    assert gateway.features["dep_latency_mean"] == 0.0
