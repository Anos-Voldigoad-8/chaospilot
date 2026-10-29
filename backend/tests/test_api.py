"""Smoke tests for health, service registry and overview."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["simulation_mode"] is True
    assert payload["llm_provider"] == "openai"


def test_services_are_seeded_with_metrics(client: TestClient) -> None:
    response = client.get("/api/services")
    assert response.status_code == 200
    services = response.json()
    assert {service["id"] for service in services} == {
        "catalog",
        "cart",
        "checkout",
        "payments",
        "notifications",
    }
    checkout = next(service for service in services if service["id"] == "checkout")
    assert set(checkout["dependencies"]) == {"cart", "payments", "notifications"}
    assert checkout["latest"] is not None
    assert checkout["status"] in {"healthy", "degraded"}
    assert checkout["active_faults"] == 0


def test_overview_snapshot(client: TestClient) -> None:
    response = client.get("/api/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["services_total"] == 5
    assert len(payload["latest_metrics"]) == 5
    assert all("timestamp" in point for point in payload["latest_metrics"])
    assert payload["llm"]["mode"] == "fallback"


def test_unknown_service_returns_404(client: TestClient) -> None:
    response = client.get("/api/services/does-not-exist")
    assert response.status_code == 404
