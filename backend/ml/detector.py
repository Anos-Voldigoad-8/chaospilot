"""Load the Phase 5 Isolation Forest and score one feature window."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from ml.features import FEATURE_NAMES

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
DEFAULT_MODEL_PATH = MODEL_DIR / "isolation_forest.joblib"


class AnomalyDetector:
    """Calibrated wrapper: ``score(window)`` returns an anomaly score in 0-1."""

    def __init__(
        self,
        model: Any,
        *,
        feature_names: Sequence[str] = FEATURE_NAMES,
        center: float = 0.0,
        scale: float = 1.0,
        threshold: float = 0.5,
    ) -> None:
        self.model = model
        self.feature_names = tuple(feature_names)
        self.center = float(center)
        self.scale = max(float(scale), 1e-9)
        self.threshold = float(threshold)

    @classmethod
    def load(cls, path: str | Path | None = None) -> AnomalyDetector:
        """Restore the bundle written by ``ml.train``."""
        bundle = joblib.load(path or DEFAULT_MODEL_PATH)
        return cls(
            bundle["model"],
            feature_names=bundle.get("feature_names", FEATURE_NAMES),
            center=bundle.get("center", 0.0),
            scale=bundle.get("scale", 1.0),
            threshold=bundle.get("threshold", 0.5),
        )

    def score(self, window: Any) -> float:
        """Return an anomaly score in 0-1 for a window or feature mapping.

        ``window`` may be an :class:`ml.features.Window`, a mapping of feature
        name to value, or a sequence in :attr:`feature_names` order.
        """
        vector = self._vector(window)
        decision = float(self.model.decision_function(vector.reshape(1, -1))[0])
        return round(self._calibrate(decision), 4)

    def is_anomaly(self, window: Any) -> bool:
        """True when the calibrated score crosses the stored threshold."""
        return self.score(window) >= self.threshold

    def _vector(self, window: Any) -> np.ndarray:
        if isinstance(window, Mapping):
            missing = [name for name in self.feature_names if name not in window]
            if missing:
                raise ValueError(f"window is missing features: {', '.join(missing)}")
            values = [window[name] for name in self.feature_names]
        elif hasattr(window, "features"):
            return self._vector(window.features)
        elif isinstance(window, Sequence):
            values = list(window)
        else:
            raise TypeError("score() expects a Window, mapping or feature sequence")

        if len(values) != len(self.feature_names):
            raise ValueError(
                f"expected {len(self.feature_names)} features, got {len(values)}"
            )
        vector = np.asarray(values, dtype=float)
        if not np.all(np.isfinite(vector)):
            raise ValueError("features must be finite numbers")
        return vector

    def _calibrate(self, decision: float) -> float:
        exponent = (decision - self.center) / self.scale
        if exponent >= 60.0:
            return 0.0
        if exponent <= -60.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(exponent))
