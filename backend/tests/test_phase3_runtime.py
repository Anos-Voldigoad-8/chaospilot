"""Phase 3 status derivation and the Phase 7 resilience formula."""

from __future__ import annotations

from runtime import derive_status, resilience_breakdown, statuses_from_rows, worst_status


def test_status_bad_when_down_or_error() -> None:
    assert derive_status(up=False, error=True, latency_ms=1.0, baseline_ms=10.0) == "bad"
    assert derive_status(up=True, error=True, latency_ms=1.0, baseline_ms=10.0) == "bad"


def test_status_warn_only_above_three_times_baseline() -> None:
    assert derive_status(up=True, error=False, latency_ms=30.0, baseline_ms=10.0) == "ok"
    assert derive_status(up=True, error=False, latency_ms=30.1, baseline_ms=10.0) == "warn"
    assert derive_status(up=True, error=False, latency_ms=5.0, baseline_ms=10.0) == "ok"
    assert derive_status(up=True, error=False, latency_ms=5.0, baseline_ms=None) == "ok"


def test_worst_status_never_improves() -> None:
    assert worst_status(None, "ok") == "ok"
    assert worst_status("bad", "warn") == "bad"
    assert worst_status("ok", "warn") == "warn"
    assert worst_status("warn", "bad") == "bad"


def test_statuses_keep_the_worst_value_per_service() -> None:
    rows = [
        {"service": "payments", "up": True, "error": False, "latency_ms": 10.0},
        {"service": "payments", "up": True, "error": False, "latency_ms": 90.0},
        {"service": "payments", "up": False, "error": True, "latency_ms": 4.0},
        {"service": "db", "up": True, "error": False, "latency_ms": 50.0},
    ]
    statuses = statuses_from_rows(rows, {"payments": 10.0, "db": 10.0})
    assert statuses == {"payments": "bad", "db": "warn"}


def test_score_is_100_with_no_failed_or_degraded_services() -> None:
    breakdown = resilience_breakdown(
        {"gateway": "ok", "payments": "ok"},
        fixes=False,
        blast_radius={"gateway", "payments"},
    )
    assert breakdown["value"] == 100.0
    assert breakdown["failed"] == []
    assert breakdown["degraded"] == []
    assert breakdown["contained"] is True
    assert breakdown["bonus"] == 0.0


def test_score_subtracts_per_failed_and_degraded_service() -> None:
    breakdown = resilience_breakdown(
        {
            "gateway": "bad",
            "orders": "bad",
            "payments": "warn",
            "auth": "ok",
        },
        fixes=False,
        blast_radius={"gateway", "orders", "payments"},
    )
    assert breakdown["failed"] == ["gateway", "orders"]
    assert breakdown["degraded"] == ["payments"]
    assert breakdown["value"] == 100.0 - 2 * 15.0 - 6.0


def test_score_bonus_requires_fixes_and_containment() -> None:
    statuses = {"payments": "warn", "db": "ok", "cache": "ok"}
    contained = resilience_breakdown(
        statuses, fixes=True, blast_radius={"payments", "orders"}
    )
    assert contained["contained"] is True
    assert contained["bonus"] == 10.0
    assert contained["value"] == 100.0

    without_fixes = resilience_breakdown(
        statuses, fixes=False, blast_radius={"payments", "orders"}
    )
    assert without_fixes["bonus"] == 0.0
    assert without_fixes["value"] == 94.0

    leaked = resilience_breakdown(
        {"payments": "warn", "db": "bad"},
        fixes=True,
        blast_radius={"payments", "orders"},
    )
    assert leaked["contained"] is False
    assert leaked["bonus"] == 0.0


def test_score_is_clamped_to_zero() -> None:
    statuses = {f"svc-{index}": "bad" for index in range(10)}
    breakdown = resilience_breakdown(statuses, fixes=False, blast_radius=statuses)
    assert breakdown["value"] == 0.0
