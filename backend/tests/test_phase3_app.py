"""Phase 3 API, WebSocket stream and experiment lifecycle."""

from __future__ import annotations

import asyncio
import inspect
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from api_config import ApiSettings
from app import create_app
from db import Sample
from service_map import ALL_SERVICES


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def _result(self, action: str, service: str, **extra: Any) -> dict[str, Any]:
        self.calls.append((action, service))
        return {"ok": True, "action": action, "service": service, **extra}

    def kill(self, service: str) -> dict[str, Any]:
        return self._result("kill", service)

    def restore(self, service: str) -> dict[str, Any]:
        return self._result("restore", service)

    def latency(self, service: str, ms: float) -> dict[str, Any]:
        return self._result("latency", service, latency_ms=ms)

    def memory(self, service: str, mb: int) -> dict[str, Any]:
        return self._result("memory", service, memory_mb=mb)

    def reset_all(self) -> dict[str, Any]:
        return {"ok": True, "action": "reset_all", "services": {}}


class FakeStack:
    def __init__(self) -> None:
        self.restart_calls: list[bool] = []

    async def restart(self, *, resilient: bool) -> dict[str, Any]:
        self.restart_calls.append(resilient)
        return {"ok": True, "resilient": resilient, "duration_ms": 1.0}

    async def wait_healthy(self, *, timeout: float | None = None) -> dict[str, Any]:
        return {"ok": True, "unreachable": [], "checked": {}}


class FakeCollector:
    """Emits one synthetic batch every 20ms instead of probing the stack."""

    def __init__(
        self,
        database,
        *,
        label_resolver,
        on_samples,
        interval: float = 0.02,
    ) -> None:
        self.database = database
        self.label_resolver = label_resolver
        self.on_samples = on_samples
        self.interval = interval
        self.task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self.task is None:
            return
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task
        self.task = None

    async def _run(self) -> None:
        while True:
            now = time.time()
            experiment_id, label = self.label_resolver(now)
            latency = 400.0 if label else 10.0
            samples = [
                Sample(
                    ts=now,
                    service=service,
                    up=True,
                    latency_ms=latency,
                    error=False,
                    label=label,
                    experiment_id=experiment_id,
                )
                for service in ALL_SERVICES
            ]
            self.database.insert_samples(samples)
            result = self.on_samples(samples)
            if inspect.isawaitable(result):
                await result
            await asyncio.sleep(self.interval)


def fake_collector_factory(database, *, label_resolver, on_samples):
    return FakeCollector(
        database, label_resolver=label_resolver, on_samples=on_samples
    )


def build_app(tmp_path: Path):
    settings = ApiSettings(
        db_path=tmp_path / "phase3.db",
        baseline_seconds=0.15,
        fault_seconds=0.25,
        recovery_seconds=0.15,
        collector_interval=0.02,
    )
    engine = FakeEngine()
    stack = FakeStack()
    app = create_app(
        settings,
        engine=engine,
        stack=stack,
        collector_factory=fake_collector_factory,
    )
    return app, engine, stack


def wait_until_idle(client: TestClient, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not client.get("/health").json()["experiment_running"]:
            return
        time.sleep(0.02)
    raise AssertionError("experiment did not finish")


def test_topology_and_cors(tmp_path: Path) -> None:
    app, _, _ = build_app(tmp_path)
    with TestClient(app) as client:
        topology = client.get("/topology").json()
        assert {node["id"] for node in topology["nodes"]} == set(ALL_SERVICES)
        assert len(topology["edges"]) == 6
        assert {edge["source"] for edge in topology["edges"]} == {
            "gateway",
            "auth",
            "orders",
            "payments",
        }

        preflight = client.options(
            "/topology",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.status_code == 200
        assert (
            preflight.headers["access-control-allow-origin"]
            == "http://localhost:5173"
        )


def test_invalid_target_is_rejected(tmp_path: Path) -> None:
    app, _, _ = build_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/experiments/run",
            json={"fault": "latency", "target": "not-a-service", "fixes": False},
        )
        assert response.status_code == 400
        assert "unknown service" in response.json()["detail"]


def test_experiment_streams_events_and_persists(tmp_path: Path) -> None:
    app, engine, stack = build_app(tmp_path)
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            welcome = websocket.receive_json()
            assert welcome["type"] == "log"

            response = client.post(
                "/experiments/run",
                json={"fault": "latency", "target": "payments", "fixes": False},
            )
            assert response.status_code == 202
            experiment_id = response.json()["id"]

            events: list[dict[str, Any]] = []
            for _ in range(2_000):
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "postmortem":
                    break
            else:
                raise AssertionError("no postmortem event received")

        types = {event["type"] for event in events}
        assert {"state", "metrics", "score", "postmortem", "log"} <= types
        assert all(
            event["status"] in {"ok", "warn", "bad"}
            for event in events
            if event["type"] == "state"
        )
        assert any(
            event["status"] == "warn"
            for event in events
            if event["type"] == "state"
        )
        metrics = next(event for event in events if event["type"] == "metrics")
        assert {"gateway_latency", "error_rate"} <= metrics.keys()
        assert metrics["gateway_latency"] > 0

        assert engine.calls == [("latency", "payments")]
        assert stack.restart_calls == []

        wait_until_idle(client)
        history = client.get("/experiments").json()
        assert history["count"] == 1
        assert history["experiments"][0]["id"] == experiment_id

        detail = client.get(f"/experiments/{experiment_id}").json()
        assert detail["status"] == "completed"
        assert detail["fault"] == "latency"
        assert detail["target"] == "payments"
        assert detail["sample_count"] > 0
        assert detail["labels"]["normal"] > 0
        assert detail["labels"]["fault"] > 0
        assert set(detail["phases"]) == {"baseline", "fault", "recovery"}
        assert (
            detail["phases"]["fault"]["p50_ms"]
            > detail["phases"]["baseline"]["p50_ms"] * 3
        )
        assert detail["postmortem"].startswith(f"Experiment #{experiment_id}")
        assert 0 < detail["score"] <= 100

        missing = client.get("/experiments/999999")
        assert missing.status_code == 404


def test_fixes_restarts_stack_with_resilient_mode(tmp_path: Path) -> None:
    app, _, stack = build_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/experiments/run",
            json={"fault": "memory", "target": "db", "fixes": True},
        )
        assert response.status_code == 202
        experiment_id = response.json()["id"]
        wait_until_idle(client)

        assert stack.restart_calls == [True]
        detail = client.get(f"/experiments/{experiment_id}").json()
        assert detail["fixes"] is True
        assert detail["resilient"] is True
        assert detail["status"] == "completed"


def test_kill_fault_restores_the_target(tmp_path: Path) -> None:
    app, engine, _ = build_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/experiments/run",
            json={"fault": "kill", "target": "cache", "fixes": False},
        )
        assert response.status_code == 202
        experiment_id = response.json()["id"]
        wait_until_idle(client)

        assert ("kill", "cache") in engine.calls
        assert ("restore", "cache") in engine.calls
        assert client.get(f"/experiments/{experiment_id}").json()["status"] == "completed"

