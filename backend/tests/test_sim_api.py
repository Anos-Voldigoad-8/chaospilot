"""API tests for the simulator-based app (backend/app.py)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from api_config import ApiSettings
from app import create_app
from db import ChaosDatabase


def _app(tmp_path):
    database = ChaosDatabase(tmp_path / "api.db")
    settings = ApiSettings(db_path=tmp_path / "settings.db")
    return create_app(settings, database=database), database


def test_health_and_topology(tmp_path) -> None:
    app, _ = _app(tmp_path)
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["status"] == "ok"
        topology = client.get("/topology").json()
        assert {node["id"] for node in topology["nodes"]} == {
            "gateway",
            "auth",
            "orders",
            "payments",
            "cache",
            "db",
        }
        assert {edge["source"] + "->" + edge["target"] for edge in topology["edges"]} == {
            "gateway->auth",
            "gateway->orders",
            "auth->cache",
            "orders->payments",
            "orders->db",
            "payments->db",
        }


def test_scenarios_collect_and_experiment(tmp_path) -> None:
    app, database = _app(tmp_path)
    # Seed one scenario directly so the list is non-empty without network.
    database.insert_scenario(
        fault_type="latency",
        target_service="payments",
        duration_minutes=0.5,
        severity="high",
        load_curve=[],
        source="seed",
        source_url="scripts/build_seed.py",
        data_source="seed",
        title="seed latency on payments",
    )
    with TestClient(app) as client:
        scenarios = client.get("/scenarios").json()
        assert scenarios["count"] == 1
        scenario_id = scenarios["scenarios"][0]["id"]
        assert scenarios["scenarios"][0]["data_source"] == "seed"

        # Run the experiment end to end (it runs in the background; poll).
        response = client.post(
            "/experiments/run",
            json={"scenario_id": scenario_id, "fixes": False},
        )
        assert response.status_code == 202, response.text
        run = response.json()
        assert run["scenario_id"] == scenario_id
        assert run["fault_type"] == "latency"
        assert run["target_service"] == "payments"

        # The experiment pauses in the broken (fault) state awaiting a fix.
        detail = None
        for _ in range(200):
            detail = client.get(f"/experiments/{run['id']}").json()
            if detail.get("status") == "fault":
                break
            time.sleep(0.1)
        assert detail is not None
        assert detail["status"] == "fault", detail
        assert detail.get("fault_ended") is None, "should be awaiting fix"

        # Apply the fix -> recovery completes.
        resolve = client.post(f"/experiments/{run['id']}/resolve")
        assert resolve.status_code == 200, resolve.text
        assert resolve.json()["status"] == "recovery"

        for _ in range(200):
            detail = client.get(f"/experiments/{run['id']}").json()
            if detail.get("status") not in ("pending", "running", "baseline", "fault", "recovery"):
                break
            time.sleep(0.1)
        assert detail is not None
        assert detail["status"] == "completed", detail
        assert detail["score"] is not None
        assert detail["postmortem"]
        assert "scenario" in detail["postmortem"]

        # Experiment shows up in history.
        listed = client.get("/experiments").json()["experiments"]
        assert any(item["id"] == run["id"] for item in listed)


def test_resolve_requires_active_fault_experiment(tmp_path) -> None:
    app, _ = _app(tmp_path)
    with TestClient(app) as client:
        # No active experiment.
        response = client.post("/experiments/1/resolve")
        assert response.status_code == 400


def test_stop_aborts_active_experiment_and_allows_new_run(tmp_path) -> None:
    app, database = _app(tmp_path)
    database.insert_scenario(
        fault_type="latency",
        target_service="payments",
        duration_minutes=0.5,
        severity="high",
        load_curve=[],
        source="seed",
        source_url="scripts/build_seed.py",
        data_source="seed",
        title="seed latency on payments",
    )
    with TestClient(app) as client:
        # Start an experiment; it pauses in the fault state.
        run = client.post(
            "/experiments/run", json={"scenario_id": 1, "fixes": False}
        ).json()
        for _ in range(200):
            detail = client.get(f"/experiments/{run['id']}").json()
            if detail.get("status") == "fault":
                break
            time.sleep(0.1)
        assert detail["status"] == "fault", detail

        # Stop it.
        stopped = client.post(f"/experiments/{run['id']}/stop")
        assert stopped.status_code == 200, stopped.text
        assert stopped.json()["status"] == "stopped"

        # The background task updates the run status to "stopped".
        detail = None
        for _ in range(200):
            detail = client.get(f"/experiments/{run['id']}").json()
            if detail.get("status") == "stopped":
                break
            time.sleep(0.1)
        assert detail is not None
        assert detail["status"] == "stopped", detail

        # A new experiment can now be started (runner is no longer busy).
        run2 = client.post(
            "/experiments/run", json={"scenario_id": 1, "fixes": False}
        ).json()
        assert run2["status"] == "pending"
        assert run2["id"] != run["id"]


def test_stop_requires_active_experiment(tmp_path) -> None:
    app, _ = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/experiments/1/stop")
        assert response.status_code == 400


def test_unknown_scenario_rejected(tmp_path) -> None:
    app, _ = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/experiments/run", json={"scenario_id": 99999, "fixes": False}
        )
        assert response.status_code == 400


def test_agent_collect_produces_scenarios_offline(tmp_path) -> None:
    app, database = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/agent/collect")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["count"] >= 1
        # Every scenario carries a data-source badge.
        for scenario in payload["scenarios"]:
            assert scenario["data_source"] in {"live", "cached", "seed"}
            assert scenario["source_url"]
