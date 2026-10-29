"""Phase 2 chaos engine contracts (no Docker daemon required)."""

from __future__ import annotations

from chaos.engine import ChaosEngine
from service_map import ALL_SERVICES


def test_latency_rejects_out_of_range_values() -> None:
    engine = ChaosEngine()
    for value in (-1, 60_001):
        result = engine.latency("payments", value)
        assert result["action"] == "latency"
        assert result["ok"] is False
        assert "between 0 and 60000" in result["error"]


def test_memory_rejects_out_of_range_values() -> None:
    engine = ChaosEngine()
    for value in (-1, 1_025):
        result = engine.memory("payments", value)
        assert result["action"] == "memory"
        assert result["ok"] is False
        assert "between 0 and 1024" in result["error"]


def test_unknown_service_is_rejected() -> None:
    engine = ChaosEngine()
    for action in (
        engine.kill("unknown"),
        engine.restore("unknown"),
        engine.latency("unknown", 100),
        engine.memory("unknown", 10),
    ):
        assert action["ok"] is False
        assert action["error"] == "unknown service: unknown"


def test_kill_reports_docker_failure(monkeypatch) -> None:
    engine = ChaosEngine()

    def missing_container(service: str):
        raise RuntimeError(f"no container for {service}")

    monkeypatch.setattr(engine, "_container", missing_container)
    result = engine.kill("payments")

    assert result["action"] == "kill"
    assert result["service"] == "payments"
    assert result["ok"] is False
    assert "no container for payments" in result["error"]


def test_reset_all_calls_every_service(monkeypatch) -> None:
    engine = ChaosEngine()
    calls: list[str] = []

    def fake_post(action: str, service: str, path: str, payload: dict):
        calls.append(service)
        assert path == "/_chaos/reset"
        assert payload == {}
        return {"action": action, "service": service, "ok": True}

    monkeypatch.setattr(engine, "_post_chaos", fake_post)
    result = engine.reset_all()

    assert result["action"] == "reset_all"
    assert result["ok"] is True
    assert set(calls) == set(ALL_SERVICES)
    assert set(result["services"]) == set(ALL_SERVICES)
    assert all(item["ok"] for item in result["services"].values())
