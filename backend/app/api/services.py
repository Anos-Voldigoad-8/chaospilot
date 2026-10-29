"""Service and metric read endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db
from app.api.schemas import MetricsResponse, MetricSummary, ServiceOut
from app.api.serializers import to_metric, to_service
from app.database import Database
from app.services import store

router = APIRouter(tags=["services"])


def _latest_map(database: Database) -> dict[str, dict]:
    return {row["service_id"]: row for row in store.latest_metrics(database)}


def _active_counts(database: Database) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fault in store.active_faults(database):
        counts[fault["service_id"]] = counts.get(fault["service_id"], 0) + 1
    return counts


@router.get("/api/services", response_model=list[ServiceOut])
def list_services(database: Database = Depends(get_db)) -> list[dict]:
    latest = _latest_map(database)
    active = _active_counts(database)
    return [
        to_service(row, latest.get(row["id"]), active.get(row["id"], 0))
        for row in store.list_services(database)
    ]


@router.get("/api/services/{service_id}", response_model=ServiceOut)
def get_service(service_id: str, database: Database = Depends(get_db)) -> dict:
    row = store.get_service(database, service_id)
    if row is None:
        raise HTTPException(status_code=404, detail="service not found")
    latest = store.latest_metric(database, service_id)
    active = _active_counts(database).get(service_id, 0)
    return to_service(row, latest, active)


@router.get("/api/metrics", response_model=MetricsResponse)
def get_metrics(
    service_id: str | None = Query(default=None),
    minutes: int = Query(default=15, ge=1, le=1440),
    database: Database = Depends(get_db),
) -> dict:
    since = time.time() - minutes * 60
    if service_id and store.get_service(database, service_id) is None:
        raise HTTPException(status_code=404, detail="service not found")

    points: list[dict] = []
    for service in store.list_services(database):
        if service_id and service["id"] != service_id:
            continue
        points.extend(
            to_metric(row) for row in store.metrics_since(database, service["id"], since)
        )
    points.sort(key=lambda item: item["timestamp"])
    return {"service_id": service_id, "minutes": minutes, "points": points}


@router.get("/api/metrics/summary", response_model=list[MetricSummary])
def metrics_summary(
    minutes: int = Query(default=60, ge=1, le=1440),
    database: Database = Depends(get_db),
) -> list[dict]:
    since = time.time() - minutes * 60
    summaries: list[dict] = []
    for service in store.list_services(database):
        rows = store.metrics_since(database, service["id"], since)
        samples = len(rows)
        if not samples:
            continue
        summaries.append(
            {
                "service_id": service["id"],
                "avg_latency_ms": round(sum(row["latency_ms"] for row in rows) / samples, 2),
                "avg_error_rate": round(sum(row["error_rate"] for row in rows) / samples, 4),
                "avg_cpu_percent": round(sum(row["cpu_percent"] for row in rows) / samples, 2),
                "avg_memory_mb": round(sum(row["memory_mb"] for row in rows) / samples, 2),
                "avg_request_rate": round(sum(row["request_rate"] for row in rows) / samples, 2),
                "samples": samples,
            }
        )
    return summaries
