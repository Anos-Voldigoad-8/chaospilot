"""Agent tests: deterministic fallback, incident persistence, no secret leakage."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.agent.llm import build_client
from app.config import LLMSettings


def test_agent_status_does_not_expose_key(client: TestClient) -> None:
    response = client.get("/api/agent/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "fallback"
    assert "api_key" not in payload
    assert "key" not in {name.lower() for name in payload}


def test_diagnose_uses_fallback_and_persists_incident(client: TestClient) -> None:
    response = client.post(
        "/api/agent/diagnose", json={"service_id": "checkout"}
    )
    assert response.status_code == 200
    incident = response.json()
    assert incident["service_id"] == "checkout"
    assert incident["provider"] == "fallback"
    assert incident["summary"]
    assert incident["root_cause"]
    assert isinstance(incident["evidence"], list)
    assert incident["recommendations"]

    listed = client.get("/api/incidents").json()
    assert any(item["id"] == incident["id"] for item in listed)

    fetched = client.get(f"/api/incidents/{incident['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == incident["id"]


def test_diagnose_includes_injected_fault_evidence(client: TestClient) -> None:
    client.post(
        "/api/faults",
        json={
            "service_id": "payments",
            "fault_type": "error",
            "duration_seconds": 120,
            "parameters": {"error_rate": 0.8},
        },
    )
    response = client.post("/api/agent/diagnose", json={"service_id": "payments"})
    assert response.status_code == 200
    payload = response.json()
    assert any("fault" in item.lower() for item in payload["evidence"])
    assert payload["confidence"] >= 0.5


def test_diagnose_unknown_service(client: TestClient) -> None:
    response = client.post("/api/agent/diagnose", json={"service_id": "ghost"})
    assert response.status_code == 404


def test_placeholder_api_key_is_not_used() -> None:
    settings = LLMSettings(
        _env_file=None,
        LLM_PROVIDER="openai",
        OPENAI_API_KEY="your-openai-api-key-here",
    )
    assert settings.api_key is None
    assert build_client(settings) is None


def test_openai_client_requires_real_key() -> None:
    settings = LLMSettings(
        _env_file=None,
        LLM_PROVIDER="openai",
        OPENAI_API_KEY="placeholder-for-tests",
    )
    client = build_client(settings)
    assert client is not None
    assert client.name == "openai"
    assert "placeholder-for-tests" not in repr(settings)
