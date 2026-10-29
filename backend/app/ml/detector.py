"""Isolation Forest anomaly detector with an explainable statistical fallback.

The model is intentionally small. Robust per-feature deviations are always
computed so the agent can explain *which* signal moved, even when the
Isolation Forest provides the anomaly decision.
"""

from __future__ import annotations

import math
import pickle
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.features import FEATURE_NAMES

try:  # scikit-learn is a hard dependency, but degrade gracefully if absent.
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in minimal installs
    IsolationForest = None  # type: ignore[assignment]
    StandardScaler = None  # type: ignore[assignment]
    SKLEARN_AVAILABLE = False

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
ANOMALY_Z_THRESHOLD = 3.5


@dataclass(frozen=True)
class DetectionResult:
    score: float
    is_anomaly: bool
    severity: str
    top_feature: str
    deviations: dict[str, float] = field(default_factory=dict)
    model_flagged: bool = False

    @property
    def explanation(self) -> str:
        label = FEATURE_NAMES[0] if not self.top_feature else self.top_feature
        deviation = self.deviations.get(label, 0.0)
        return f"{label} deviates {deviation:.1f} robust standard deviations"


def _mad(values: np.ndarray) -> np.ndarray:
    median = np.median(values, axis=0)
    deviation = np.abs(values - median)
    mad = np.median(deviation, axis=0)
    # 1.4826 scales MAD to standard deviation for normal data. Guard zeros.
    return np.where(mad > 1e-9, mad * 1.4826, 1.0)


class AnomalyDetector:
    """Trainable detector with persistence and a cold-start heuristic."""

    def __init__(self, contamination: float = 0.04, random_state: int = 42) -> None:
        self.contamination = contamination
        self.random_state = random_state
        self.model: Any | None = None
        self.scaler: Any | None = None
        self.median: np.ndarray | None = None
        self.mad: np.ndarray | None = None
        self.samples_fitted = 0

    @property
    def is_fitted(self) -> bool:
        return self.median is not None

    def fit(self, samples: Sequence[Sequence[float]]) -> int:
        matrix = np.asarray(samples, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] < 10:
            raise ValueError("need at least 10 samples with 5 features")
        if matrix.shape[1] != len(FEATURE_NAMES):
            raise ValueError(f"expected {len(FEATURE_NAMES)} features")

        self.median = np.median(matrix, axis=0)
        self.mad = _mad(matrix)
        self.samples_fitted = int(matrix.shape[0])

        if SKLEARN_AVAILABLE:
            self.scaler = StandardScaler().fit(matrix)
            scaled = self.scaler.transform(matrix)
            contamination = min(max(self.contamination, 0.001), 0.5)
            self.model = IsolationForest(
                n_estimators=150,
                contamination=contamination,
                random_state=self.random_state,
                n_jobs=1,
            ).fit(scaled)
        else:  # pragma: no cover
            self.model = None
            self.scaler = None
        return self.samples_fitted

    def _deviations(self, sample: Sequence[float]) -> dict[str, float]:
        if self.median is None or self.mad is None:
            return {}
        vector = np.asarray(sample, dtype=float)
        z_scores = np.abs(vector - self.median) / self.mad
        return {
            name: round(float(value), 3)
            for name, value in zip(FEATURE_NAMES, z_scores, strict=True)
        }

    def score(self, sample: Sequence[float]) -> DetectionResult:
        vector = np.asarray(sample, dtype=float)
        if vector.shape[0] != len(FEATURE_NAMES):
            raise ValueError(f"expected {len(FEATURE_NAMES)} features")
        deviations = self._deviations(sample)
        max_z = max(deviations.values(), default=0.0)
        top_feature = max(deviations, key=deviations.get) if deviations else "latency_ms"

        model_flagged = False
        if self.model is not None and self.scaler is not None:
            scaled = self.scaler.transform(vector.reshape(1, -1))
            model_flagged = bool(self.model.predict(scaled)[0] == -1)

        is_anomaly = model_flagged or max_z >= ANOMALY_Z_THRESHOLD
        score = min(1.0, max(max_z / 8.0, 0.5 if model_flagged else 0.0))

        if max_z >= 8.0:
            severity = "critical"
        elif max_z >= 6.0:
            severity = "high"
        elif max_z >= 4.0 or model_flagged:
            severity = "medium"
        else:
            severity = "low"

        return DetectionResult(
            score=round(score, 4),
            is_anomaly=is_anomaly,
            severity=severity,
            top_feature=top_feature,
            deviations=deviations,
            model_flagged=model_flagged,
        )

    def heuristic_score(self, sample: Sequence[float]) -> DetectionResult:
        """Cold-start path when no model has been trained yet."""
        values = dict(zip(FEATURE_NAMES, (float(v) for v in sample), strict=True))
        checks = {
            "latency_ms": values["latency_ms"] / 500.0,
            "error_rate": values["error_rate"] / 0.2,
            "cpu_percent": values["cpu_percent"] / 85.0,
            "memory_mb": values["memory_mb"] / 1200.0,
            "request_rate": 0.0,
        }
        top_feature = max(checks, key=checks.get)
        peak = checks[top_feature]
        is_anomaly = peak >= 1.0
        severity = "critical" if peak >= 2.0 else "high" if peak >= 1.5 else "medium"
        return DetectionResult(
            score=round(min(1.0, peak), 4),
            is_anomaly=is_anomaly,
            severity=severity if is_anomaly else "low",
            top_feature=top_feature,
            deviations={top_feature: round(peak * 4, 3)},
            model_flagged=False,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            pickle.dump(
                {
                    "model": self.model,
                    "scaler": self.scaler,
                    "median": self.median,
                    "mad": self.mad,
                    "samples_fitted": self.samples_fitted,
                    "contamination": self.contamination,
                },
                handle,
            )

    @classmethod
    def load(cls, path: Path) -> AnomalyDetector | None:
        if not path.exists():
            return None
        try:
            with path.open("rb") as handle:
                payload = pickle.load(handle)  # noqa: S301 - local trusted artifact
        except (OSError, pickle.UnpicklingError, EOFError):
            return None
        detector = cls(contamination=float(payload.get("contamination", 0.04)))
        detector.model = payload.get("model")
        detector.scaler = payload.get("scaler")
        detector.median = payload.get("median")
        detector.mad = payload.get("mad")
        detector.samples_fitted = int(payload.get("samples_fitted", 0))
        return detector


def sigmoid(value: float) -> float:
    """Convenience helper for tests / future score calibration."""
    if value < -60:
        return 0.0
    if value > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-value))
