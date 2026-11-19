"""Data agent tests: mapper, scenario conversion, fallback chain."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from agent import data_agent as data_agent_module
from agent.data_agent import DataAgent
from db import ChaosDatabase


class _FakeResponse:
    def __init__(self, status_code: int, json_data: Any) -> None:
        self.status_code = status_code
        self._json = json_data

    def json(self) -> Any:
        return self._json


class _FailingClient:
    """httpx-like client that always raises (network down)."""

    async def get(self, url: str) -> _FakeResponse:
        raise httpx.ConnectError("network is down")


def test_mapper_maps_real_components_to_simulated_services() -> None:
    cases = {
        "API Gateway outage": "gateway",
        "Auth service down": "auth",
        "Orders service degraded": "orders",
        "Payments latency spike": "payments",
        "Session cache memory pressure": "cache",
        "Database crash": "db",
    }
    for name, expected in cases.items():
        # The agent's internal mapper; import the class method indirectly.
        agent = object.__new__(DataAgent)
        assert agent._map_component(name) == expected


def test_mapper_unknown_component_defaults_to_gateway() -> None:
    agent = object.__new__(DataAgent)
    assert agent._map_component("mysterious-black-box") == "gateway"


def test_agent_fallback_chain_when_network_down(tmp_path: Path) -> None:
    db = ChaosDatabase(tmp_path / "agent-fallback.db")
    agent = DataAgent(db)
    agent._client = _FailingClient()  # type: ignore[assignment]
    # Clear any cached responses so the fallback chain reaches the seed.
    # Clear any cached responses so the fallback chain reaches the seed.
    for cache_file in data_agent_module.CACHE_DIR.glob("*.json"):
        cache_file.unlink()
    scenarios = asyncio.run(agent.collect())
    assert scenarios, "seed fallback must still produce scenarios"
    sources = {s["data_source"] for s in scenarios}
    assert "seed" in sources
    # The app still exposes scenarios even when the network is down.
    assert db.list_scenarios()


@pytest.mark.asyncio
async def test_scenario_conversion_uses_real_incident_title_and_source(tmp_path: Path) -> None:
    db = ChaosDatabase(tmp_path / "conversion.db")
    agent = DataAgent(db)
    # Craft a statuspage-like payload.
    fetched = {
        "source": "statuspage",
        "source_url": "https://www.githubstatus.com/api/v2/incidents.json",
        "data": {
            "incidents": [
                {
                    "name": "Payments API degraded performance",
                    "impact": "major",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]
        },
        "data_source": "live",
    }
    scenarios = await agent._convert(fetched)
    assert scenarios
    s = scenarios[0]
    assert s.target_service == "payments"
    assert s.fault_type == "kill"  # major -> kill
    assert s.severity == "high"
    assert s.source_url == "https://www.githubstatus.com/api/v2/incidents.json"
    assert s.data_source == "live"
    assert "Payments API" in s.title


def test_seed_dir_exists_with_required_files() -> None:
    seed = Path(__file__).resolve().parents[1] / "data" / "seed"
    assert (seed / "incidents_seed.json").exists()
    assert (seed / "load_seed.csv").exists()
    assert (seed / "metrics_seed.csv").exists()
    import json

    incidents = json.loads((seed / "incidents_seed.json").read_text())
    assert len(incidents) >= 150
