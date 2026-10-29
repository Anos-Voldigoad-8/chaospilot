"""Metrics endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_metrics_are_serialised_with_timestamps(client: TestClient) -> None:
    response = client.get("/api/metrics", params={"service_id": "catalog", "minutes": 30})
    assert response.status_code == 200
    payload = response.json()
    assert payload["service_id"] == "catalog"
    assert payload["points"]
    point = payload["points"][0]
    assert set(point) == {
        "timestamp",
        "service_id",
        "latency_ms",
        "error_rate",
        "cpu_percent",
        "memory_mb",
        "request_rate",
    }
    assert all(item["service_id"] == "catalog" for item in payload["points"])


def test_metrics_summary(client: TestClient) -> None:
    response = client.get("/api/metrics/summary", params={"minutes": 60})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 5
    assert all(row["samples"] > 0 for row in rows)
    assert all(row["avg_latency_ms"] > 0 for row in rows)
