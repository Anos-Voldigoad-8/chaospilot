"""FastAPI dependency helpers backed by app.state."""

from __future__ import annotations

from fastapi import Request

from app.agent.agent import IncidentAgent
from app.chaos.manager import ChaosManager
from app.config import AppSettings, LLMSettings
from app.database import Database
from app.ml.service import AnomalyService


def get_db(request: Request) -> Database:
    return request.app.state.database


def get_anomaly_service(request: Request) -> AnomalyService:
    return request.app.state.anomaly_service


def get_chaos_manager(request: Request) -> ChaosManager:
    return request.app.state.chaos


def get_incident_agent(request: Request) -> IncidentAgent:
    return request.app.state.agent


def get_agent_or_none(request: Request) -> IncidentAgent | None:
    return getattr(request.app.state, "agent", None)


def get_app_settings(request: Request) -> AppSettings:
    return request.app.state.settings


def get_llm_settings(request: Request) -> LLMSettings:
    return request.app.state.llm_settings


def service_status(latest: dict | None, active_faults: int = 0) -> str:
    if latest is None:
        return "unknown"
    if active_faults and latest.get("error_rate", 0) >= 0.5:
        return "down"
    if latest.get("error_rate", 0) >= 0.2 or latest.get("latency_ms", 0) >= 500:
        return "degraded"
    if active_faults:
        return "degraded"
    return "healthy"
