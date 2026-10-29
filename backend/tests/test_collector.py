"""Collector and anomaly integration tests (simulation mode)."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient


def test_fault_produces_anomaly_and_recovery_restores_baseline(client: TestClient) -> None:
    app = client.app

    baseline = client.get("/api/services/payments").json()["latest"]
    assert baseline is not None

    fault = client.post(
        "/api/faults",
        json={
            "service_id": "payments",
            "fault_type": "latency",
            "duration_seconds": 300,
            "parameters": {"latency_ms": 1500},
        },
    ).json()

    for _ in range(3):
        asyncio.run(app.state.collector.tick())

    anomalous = client.get("/api/services/payments").json()["latest"]
    assert anomalous["latency_ms"] > baseline["latency_ms"] * 3

    anomalies = client.get(
        "/api/anomalies", params={"service_id": "payments", "limit": 10}
    ).json()
    assert anomalies
    assert anomalies[0]["service_id"] == "payments"

    recovered = client.post(f"/api/faults/{fault['id']}/recover")
    assert recovered.status_code == 200

    for _ in range(3):
        asyncio.run(app.state.collector.tick())

    restored = client.get("/api/services/payments").json()["latest"]
    assert restored["latency_ms"] < 300


def test_train_endpoint_reports_samples(client: TestClient) -> None:
    response = client.post("/api/anomalies/train")
    assert response.status_code == 200
    payload = response.json()
    assert payload["trained"] is True
    assert payload["samples"] >= 30
    assert payload["services"] == 5


def test_detect_endpoint_is_idempotent_within_cooldown(client: TestClient) -> None:
    first = client.post("/api/anomalies/detect")
    second = client.post("/api/anomalies/detect")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["detected"] == 0
