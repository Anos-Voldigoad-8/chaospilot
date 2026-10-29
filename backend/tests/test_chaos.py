"""Chaos lifecycle tests (simulation engine, no Docker required)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_inject_and_recover_fault(client: TestClient) -> None:
    response = client.post(
        "/api/faults",
        json={
            "service_id": "payments",
            "fault_type": "latency",
            "duration_seconds": 120,
            "parameters": {"latency_ms": 1200},
        },
    )
    assert response.status_code == 201
    fault = response.json()
    assert fault["status"] == "active"
    assert fault["engine"] == "simulation"
    assert fault["parameters"]["latency_ms"] == 1200

    active = client.get("/api/faults", params={"status": "active"}).json()
    assert any(item["id"] == fault["id"] for item in active)

    recovered = client.post(f"/api/faults/{fault['id']}/recover")
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "recovered"
    assert recovered.json()["recovered_at"] is not None


def test_invalid_fault_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/faults",
        json={
            "service_id": "payments",
            "fault_type": "latency",
            "duration_seconds": 5,
        },
    )
    assert response.status_code == 422


def test_unknown_service_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/faults",
        json={"service_id": "nope", "fault_type": "error", "duration_seconds": 60},
    )
    assert response.status_code == 422


def test_recover_unknown_fault(client: TestClient) -> None:
    response = client.post("/api/faults/fault_missing/recover")
    assert response.status_code == 404
