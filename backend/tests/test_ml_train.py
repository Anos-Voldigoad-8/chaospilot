"""End-to-end test for dataset generation, training and detector loading."""

from __future__ import annotations

from pathlib import Path

from ml.detector import AnomalyDetector
from ml.features import FEATURE_NAMES
from ml.simulate import write_simulated_dataset
from ml.train import train_from_database


def test_train_writes_artifacts_and_detector_scores_faults(tmp_path: Path) -> None:
    database = tmp_path / "dataset.db"
    write_simulated_dataset(
        database,
        experiments=24,
        healthy_seconds=180.0,
        seed=7,
    )

    payload = train_from_database(
        database,
        model_path=tmp_path / "model.joblib",
        metrics_path=tmp_path / "metrics.json",
        confusion_path=tmp_path / "confusion.png",
        trees=30,
    )

    assert payload["dataset"]["source"] == "simulated"
    assert payload["split"]["test_fault_windows"] > 0
    assert payload["test"]["f1"] > 0.5
    assert (tmp_path / "model.joblib").exists()
    assert (tmp_path / "metrics.json").exists()
    png = (tmp_path / "confusion.png").read_bytes()
    assert png.startswith(b"\x89PNG")

    detector = AnomalyDetector.load(tmp_path / "model.joblib")
    normal = {name: 0.0 for name in FEATURE_NAMES}
    normal.update({"latency_mean": 60.0, "latency_max": 70.0, "up_ratio": 1.0})
    faulty = dict(normal)
    faulty.update({"latency_mean": 2_000.0, "latency_max": 2_400.0, "latency_slope": 500.0})

    assert 0.0 <= detector.score(normal) <= 1.0
    assert 0.0 <= detector.score(faulty) <= 1.0
    assert detector.score(faulty) > detector.score(normal)
    assert detector.is_anomaly(faulty)
