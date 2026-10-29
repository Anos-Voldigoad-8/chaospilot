"""Phase 3 status derivation and resilience scoring."""

from __future__ import annotations

from runtime import derive_status, resilience_score


def test_status_bad_when_down_or_error() -> None:
    assert derive_status(up=False, error=True, latency_ms=1.0, baseline_ms=10.0) == "bad"
    assert derive_status(up=True, error=True, latency_ms=1.0, baseline_ms=10.0) == "bad"


def test_status_warn_only_above_three_times_baseline() -> None:
    assert derive_status(up=True, error=False, latency_ms=30.0, baseline_ms=10.0) == "ok"
    assert derive_status(up=True, error=False, latency_ms=30.1, baseline_ms=10.0) == "warn"
    assert derive_status(up=True, error=False, latency_ms=5.0, baseline_ms=10.0) == "ok"
    assert derive_status(up=True, error=False, latency_ms=5.0, baseline_ms=None) == "ok"


def test_score_falls_with_latency_and_errors() -> None:
    healthy = resilience_score(
        gateway_latency=100.0, baseline_gateway=100.0, error_rate=0.0
    )
    slow = resilience_score(
        gateway_latency=2_000.0, baseline_gateway=100.0, error_rate=0.0
    )
    broken = resilience_score(
        gateway_latency=2_000.0, baseline_gateway=100.0, error_rate=0.5
    )
    assert healthy == 100.0
    assert slow < healthy
    assert broken < slow
    assert broken >= 0.0
