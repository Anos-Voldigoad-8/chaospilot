"""Anomaly endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.api.deps import get_anomaly_service, get_db
from core.api.schemas import AnomalyOut, DetectionResponse, TrainingResponse
from core.database import Database
from core.ml.service import AnomalyService
from core.services import store

router = APIRouter(tags=["anomalies"])


@router.get("/api/anomalies", response_model=list[AnomalyOut])
def list_anomalies(
    limit: int = Query(default=50, ge=1, le=500),
    service_id: str | None = Query(default=None),
    database: Database = Depends(get_db),
) -> list[dict]:
    return store.list_anomalies(database, limit=limit, service_id=service_id)


@router.post("/api/anomalies/train", response_model=TrainingResponse)
def train(anomaly_service: AnomalyService = Depends(get_anomaly_service)) -> TrainingResponse:
    result = anomaly_service.train()
    return TrainingResponse(
        trained=result.trained,
        samples=result.samples,
        services=result.services,
        model_path=result.model_path,
        reason=result.reason,
    )


@router.post("/api/anomalies/detect", response_model=DetectionResponse)
def detect(anomaly_service: AnomalyService = Depends(get_anomaly_service)) -> dict:
    detected = anomaly_service.detect()
    return {"detected": len(detected), "anomalies": detected}
