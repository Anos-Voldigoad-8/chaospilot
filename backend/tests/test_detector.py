"""Unit tests for the anomaly detector."""

from __future__ import annotations

import random
from pathlib import Path

from app.ml.detector import AnomalyDetector
from app.ml.features import FEATURE_NAMES


def _healthy_samples(count: int = 200) -> list[list[float]]:
    rng = random.Random(7)
    samples: list[list[float]] = []
    for _ in range(count):
        samples.append(
            [
                rng.gauss(50, 4),    # latency_ms
                rng.gauss(0.01, 0.003),  # error_rate
                rng.gauss(20, 2),    # cpu_percent
                rng.gauss(180, 5),   # memory_mb
                rng.gauss(40, 3),    # request_rate
            ]
        )
    return samples


def test_detects_latency_spike() -> None:
    detector = AnomalyDetector()
    detector.fit(_healthy_samples())

    healthy = detector.score([52.0, 0.01, 21.0, 181.0, 41.0])
    assert not healthy.is_anomaly

    spiking = detector.score([1500.0, 0.01, 21.0, 181.0, 41.0])
    assert spiking.is_anomaly
    assert spiking.top_feature == "latency_ms"
    assert spiking.severity in {"medium", "high", "critical"}
    assert spiking.deviations["latency_ms"] > 3.5


def test_detects_error_spike() -> None:
    detector = AnomalyDetector()
    detector.fit(_healthy_samples())
    result = detector.score([50.0, 0.9, 20.0, 180.0, 40.0])
    assert result.is_anomaly
    assert result.top_feature == "error_rate"


def test_requires_enough_samples() -> None:
    detector = AnomalyDetector()
    try:
        detector.fit(_healthy_samples(5))
    except ValueError as exc:
        assert "at least 10" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_persistence_round_trip(tmp_path: Path) -> None:
    model_path = tmp_path / "detector.pkl"
    detector = AnomalyDetector()
    detector.fit(_healthy_samples())
    detector.save(model_path)

    loaded = AnomalyDetector.load(model_path)
    assert loaded is not None
    assert loaded.is_fitted
    assert loaded.samples_fitted == detector.samples_fitted
    assert loaded.score([50.0, 0.01, 20.0, 180.0, 40.0]).top_feature in FEATURE_NAMES


def test_heuristic_cold_start() -> None:
    detector = AnomalyDetector()
    result = detector.heuristic_score([900.0, 0.01, 20.0, 180.0, 40.0])
    assert result.is_anomaly
    assert result.top_feature == "latency_ms"
