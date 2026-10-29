"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import AppSettings, LLMSettings
from app.main import create_app


@pytest.fixture
def app_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        env="test",
        db_path=str(tmp_path / "chaospilot-test.db"),
        model_dir=str(tmp_path / "models"),
        collector_enabled=False,
        simulation_mode=True,
        docker_enabled=False,
        collector_interval_seconds=0.05,
        history_minutes=60,
        cors_origins="http://localhost:5173",
    )


@pytest.fixture
def llm_settings() -> LLMSettings:
    # Force the deterministic fallback: no key means no hosted client.
    return LLMSettings(_env_file=None, LLM_PROVIDER="openai", OPENAI_API_KEY="")


@pytest.fixture
def client(app_settings: AppSettings, llm_settings: LLMSettings) -> TestClient:
    app = create_app(app_settings, llm_settings)
    with TestClient(app) as test_client:
        yield test_client
