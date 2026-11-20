"""Tests for the hardcoded fallback attack-catalog scenarios."""

from __future__ import annotations

from agent.fallback_scenarios import (
    FALLBACK_SCENARIOS,
    FallbackScenario,
    get_fallback,
)


def test_fallback_covers_all_seven_demo_scenarios() -> None:
    """The seven presentation scenarios must each have a fallback."""
    expected = {
        ("kill", "gateway"),
        ("kill", "payments"),
        ("latency", "auth"),
        ("latency", "payments"),
        ("latency", "db"),
        ("memory", "cache"),
        ("memory", "orders"),
    }
    assert set(FALLBACK_SCENARIOS) == expected


def test_get_fallback_returns_scenario() -> None:
    scenario = get_fallback("latency", "payments")
    assert isinstance(scenario, FallbackScenario)
    assert scenario.fault_type == "latency"
    assert scenario.target_service == "payments"
    assert scenario.title


def test_get_fallback_unknown_returns_none() -> None:
    assert get_fallback("kill", "db") is None


def test_fault_phase_is_obviously_broken() -> None:
    for scenario in FALLBACK_SCENARIOS.values():
        f = scenario.fault
        # Target service is down/degraded and latency is spiked.
        assert f.service_statuses[scenario.target_service] in ("bad", "warn")
        assert f.latency_ms >= 400.0
        assert f.error_rate >= 0.05
        assert 0.7 <= f.anomaly_score <= 0.95
        assert 15 <= f.resilience_score <= 35


def test_recovery_phase_is_healed() -> None:
    for scenario in FALLBACK_SCENARIOS.values():
        r = scenario.recovery
        assert all(status == "ok" for status in r.service_statuses.values())
        assert r.error_rate == 0.0
        assert r.anomaly_score < 0.1
        assert 75 <= r.resilience_score <= 95


def test_postmortems_are_detailed() -> None:
    for scenario in FALLBACK_SCENARIOS.values():
        text = scenario.postmortem
        assert "Root cause:" in text
        assert "Impact:" in text
        assert "Detection:" in text
        assert "Resolution:" in text
        assert "Metrics:" in text
        assert "Recommendation:" in text
        assert len(text.splitlines()) >= 6
