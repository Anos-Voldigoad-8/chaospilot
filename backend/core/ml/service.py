"""Train, persist and apply the anomaly detector against collected metrics."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.database import Database
from core.ml.detector import AnomalyDetector
from core.ml.features import row_to_vector
from core.services import store
from core.services.registry import SERVICES

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrainingResult:
    trained: bool
    samples: int
    services: int
    model_path: str
    reason: str = ""


class AnomalyService:
    """Facade used by the collector and the HTTP API."""

    def __init__(
        self,
        database: Database,
        model_path: Path,
        *,
        min_samples: int = 30,
        cooldown_seconds: float = 20.0,
        per_service_limit: int = 500,
    ) -> None:
        self.database = database
        self.model_path = model_path
        self.min_samples = min_samples
        self.cooldown_seconds = cooldown_seconds
        self.per_service_limit = per_service_limit
        self.detector: AnomalyDetector | None = AnomalyDetector.load(model_path)

    @property
    def is_ready(self) -> bool:
        return self.detector is not None and self.detector.is_fitted

    def _training_matrix(self) -> tuple[list[list[float]], int]:
        samples: list[list[float]] = []
        services = 0
        for service in SERVICES:
            rows = store.recent_metrics(
                self.database, service.id, limit=self.per_service_limit
            )
            if not rows:
                continue
            services += 1
            samples.extend(row_to_vector(row) for row in rows)
        return samples, services

    def train(self) -> TrainingResult:
        samples, services = self._training_matrix()
        if len(samples) < self.min_samples:
            return TrainingResult(
                trained=False,
                samples=len(samples),
                services=services,
                model_path=str(self.model_path),
                reason=f"need at least {self.min_samples} samples",
            )

        detector = AnomalyDetector()
        fitted = detector.fit(samples)
        detector.save(self.model_path)
        self.detector = detector
        LOGGER.info("Trained anomaly detector on %s samples (%s services)", fitted, services)
        return TrainingResult(
            trained=True,
            samples=fitted,
            services=services,
            model_path=str(self.model_path),
        )

    def ensure_ready(self) -> TrainingResult | None:
        if self.is_ready:
            return None
        return self.train()

    def _score(self, vector: list[float]) -> Any:
        if self.detector is not None and self.detector.is_fitted:
            return self.detector.score(vector)
        fallback = AnomalyDetector()
        return fallback.heuristic_score(vector)

    def detect(self) -> list[dict[str, Any]]:
        """Score each service's newest sample and persist anomalies."""
        self.ensure_ready()
        detected: list[dict[str, Any]] = []
        now = time.time()

        for service in SERVICES:
            latest = store.latest_metric(self.database, service.id)
            if not latest:
                continue

            result = self._score(row_to_vector(latest))
            if not result.is_anomaly:
                continue
            if now - store.last_anomaly_at(self.database, service.id) < self.cooldown_seconds:
                continue

            details = {
                "top_feature": result.top_feature,
                "deviations": result.deviations,
                "model_flagged": result.model_flagged,
                "explanation": result.explanation,
            }
            anomaly_id = store.record_anomaly(
                self.database,
                service_id=service.id,
                metric=result.top_feature,
                value=float(latest.get(result.top_feature, 0.0)),
                score=result.score,
                severity=result.severity,
                detected_at=now,
                details=details,
            )
            stored = store.get_anomaly(self.database, anomaly_id)
            if stored:
                detected.append(stored)
            LOGGER.info(
                "Anomaly on %s (%s, severity=%s, score=%.2f)",
                service.id,
                result.top_feature,
                result.severity,
                result.score,
            )

        return detected
