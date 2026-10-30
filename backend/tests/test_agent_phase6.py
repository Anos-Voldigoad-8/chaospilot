"""Phase 6 tests: mocked LLM planner, postmortem and safe tool fallbacks."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from agent.context import build_postmortem_context
from agent.models import ExperimentPlan
from agent.planner import Planner, rule_based_plan
from agent.postmortem import PostmortemWriter
from agent.tools import get_topology, inject_fault, read_logs, read_metrics, rollback
from api_config import ApiSettings
from app import create_app
from db import ChaosDatabase, Sample

PLAN_JSON = (
    '{"fault": "latency", "target": "payments", '
    '"hypothesis": "Delaying payments should expose missing timeouts in orders."}'
)
POSTMORTEM_JSON = (
    '{"root_cause": "Injected latency on payments slowed every checkout.", '
    '"blast_radius": "Orders, gateway and checkout users saw slower requests.", '
    '"fixes": ["Add a timeout around payment calls.", '
    '"Add a circuit breaker for payment failures.", '
    '"Alert on p95 latency versus the baseline."]}'
)


class FakeLLM:
    """A deterministic stand-in for the provider client."""

    name = "fake"
    model = "fake-1"

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.responses.pop(0)


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []

    def kill(self, service: str) -> dict[str, Any]:
        self.calls.append(("kill", service, None))
        return {"ok": True, "action": "kill", "service": service}

    def latency(self, service: str, ms: float) -> dict[str, Any]:
        self.calls.append(("latency", service, ms))
        return {"ok": True, "action": "latency", "service": service}

    def memory(self, service: str, mb: int) -> dict[str, Any]:
        self.calls.append(("memory", service, mb))
        return {"ok": True, "action": "memory", "service": service}

    def reset_all(self) -> dict[str, Any]:
        self.calls.append(("reset_all", "", None))
        return {"ok": True, "action": "reset_all", "services": {}}

    def restore(self, service: str) -> dict[str, Any]:
        self.calls.append(("restore", service, None))
        return {"ok": True, "action": "restore", "service": service}


def _postmortem_context() -> dict[str, Any]:
    return {
        "experiment": {
            "id": 1,
            "fault": "latency",
            "target": "payments",
            "fixes": False,
            "status": "completed",
            "score": 40.0,
            "error": None,
        },
        "topology": get_topology(),
        "baseline_latency_ms": {"payments": 8.0, "gateway": 62.0},
        "status_timeline": {
            "payments": [{"phase": "fault", "status": "warn", "at": 1.0, "latency_ms": 2_000.0}],
            "gateway": [{"phase": "fault", "status": "warn", "at": 1.0, "latency_ms": 2_050.0}],
        },
        "anomaly_scores": {"payments": 0.93, "gateway": 0.71},
        "affected_services": ["gateway", "orders", "payments"],
    }


def test_planner_accepts_one_valid_json_response() -> None:
    llm = FakeLLM([PLAN_JSON])
    plan = asyncio.run(Planner(llm).plan())

    assert isinstance(plan, ExperimentPlan)
    assert plan.fault == "latency"
    assert plan.target == "payments"
    assert plan.source == "llm"
    assert plan.hypothesis.endswith(".")
    assert len(llm.calls) == 1


def test_planner_falls_back_after_two_invalid_responses() -> None:
    llm = FakeLLM(["not json at all", '{"fault": "explode", "target": "db"}'])
    plan = asyncio.run(Planner(llm).plan())

    assert len(llm.calls) == 2
    assert plan.source == "rule"
    assert plan.target == "db"  # db has the most direct callers (orders, payments)
    assert "callers" in plan.hypothesis
    assert plan.fault == "latency"


def test_rule_based_planner_targets_most_called_service() -> None:
    plan = rule_based_plan(get_topology())
    assert plan.target == "db"
    assert plan.source == "rule"


def test_postmortem_uses_llm_and_stays_under_word_budget() -> None:
    long_root = " ".join(["payments stayed slow"] * 20)
    long_json = (
        '{"root_cause": "' + long_root + '", '
        '"blast_radius": "Orders and gateway degraded for checkout users.", '
        '"fixes": ["Add timeouts.", "Add a circuit breaker.", "Alert on p95 latency."]}'
    )
    report = asyncio.run(PostmortemWriter(FakeLLM([long_json])).generate(_postmortem_context()))

    assert report.source == "llm"
    assert len(report.fixes) == 3
    assert report.word_count <= 120
    assert report.text.startswith("Root cause:")
    assert "Blast radius:" in report.text
    assert "Fixes:" in report.text


def test_postmortem_falls_back_to_template_when_llm_fails() -> None:
    report = asyncio.run(PostmortemWriter(FakeLLM(["not-json"])).generate(_postmortem_context()))

    assert report.source == "template"
    assert report.root_cause
    assert "payments" in report.blast_radius or "orders" in report.blast_radius
    assert len(report.fixes) == 3
    assert report.word_count <= 120
    assert "Fixes:" in report.text


def test_tools_read_metrics_and_logs_from_telemetry(tmp_path: Path) -> None:
    database = ChaosDatabase(tmp_path / "tools.db")
    started = time.time() - 4.0
    database.insert_samples(
        [
            Sample(
                ts=started + index,
                service="payments",
                up=index != 2,
                latency_ms=2_000.0 if index >= 2 else 8.0,
                error=index == 2,
            )
            for index in range(4)
        ]
    )

    metrics = read_metrics("payments", database, window_seconds=60.0)
    assert metrics["samples"] == 4
    assert metrics["latency_max"] == 2_000.0
    assert metrics["error_rate"] == 0.25
    assert metrics["up_ratio"] == 0.75

    logs = read_logs("payments", database, window_seconds=60.0)
    assert logs["count"] >= 2
    assert {line["level"] for line in logs["lines"]} == {"error", "warn"}


def test_tools_inject_fault_and_rollback_with_injected_engine() -> None:
    engine = FakeEngine()
    result = inject_fault("payments", "latency", 1_500, engine=engine)
    assert result["ok"] is True
    assert engine.calls[-1] == ("latency", "payments", 1_500.0)

    rollback_result = rollback(engine=engine)
    assert rollback_result["ok"] is True
    assert rollback_result["action"] == "rollback"
    assert ("reset_all", "", None) in engine.calls
    assert {call[1] for call in engine.calls if call[0] == "restore"} == {
        "gateway",
        "auth",
        "orders",
        "cache",
        "payments",
        "db",
    }


def test_context_contains_timeline_scores_and_fix_flag(tmp_path: Path) -> None:
    database = ChaosDatabase(tmp_path / "context.db")
    started = 1_000.0
    experiment_id = database.start_experiment("latency", "payments", started=started)
    database.create_run(experiment_id)
    database.update_run(
        experiment_id,
        status="completed",
        baseline_end=started + 5.0,
        fault_started=started + 5.0,
        fault_ended=started + 15.0,
        recovery_end=started + 20.0,
    )

    samples = []
    for offset in range(20):
        moment = started + offset
        fault = 5.0 <= offset < 15.0
        for service in ("gateway", "orders", "payments", "db"):
            latency = 10.0
            if fault and service == "payments":
                latency = 2_000.0
            elif fault and service in {"gateway", "orders"}:
                latency = 400.0
            samples.append(
                Sample(
                    ts=moment,
                    service=service,
                    up=True,
                    latency_ms=latency,
                    error=False,
                    label=1 if fault else 0,
                    experiment_id=experiment_id,
                )
            )
    database.insert_samples(samples)
    database.end_experiment(experiment_id, ended=started + 20.0)

    class FakeDetector:
        def score(self, window: Any) -> float:
            return 0.9 if window.service == "payments" else 0.1

    context = build_postmortem_context(database, experiment_id, detector=FakeDetector())

    assert context["experiment"]["fixes"] is False
    assert context["experiment"]["target"] == "payments"
    assert context["anomaly_scores"]["payments"] > context["anomaly_scores"]["db"]
    assert "payments" in context["status_timeline"]
    assert any(
        event["status"] == "warn"
        for event in context["status_timeline"]["payments"]
    )
    assert set(context["affected_services"]) == {"gateway", "orders", "payments"}


def test_agent_plan_endpoint_uses_mocked_llm(tmp_path: Path) -> None:
    llm = FakeLLM([PLAN_JSON])
    settings = ApiSettings(db_path=tmp_path / "agent.db")
    app = create_app(settings, agent_llm=llm)

    with TestClient(app) as client:
        response = client.post("/agent/plan")
        assert response.status_code == 200
        payload = response.json()
        assert payload["fault"] == "latency"
        assert payload["target"] == "payments"
        assert payload["source"] == "llm"
        assert payload["hypothesis"].endswith(".")

        status = client.get("/agent/status").json()
        assert status["mode"] == "llm"
        assert status["provider"] == "fake"
        assert "key" not in status


def test_agent_plan_endpoint_falls_back_without_llm(tmp_path: Path) -> None:
    settings = ApiSettings(db_path=tmp_path / "agent-fallback.db")
    app = create_app(settings, agent_llm=None)

    with TestClient(app) as client:
        payload = client.post("/agent/plan").json()
        assert payload["source"] == "rule"
        assert payload["target"] == "db"
