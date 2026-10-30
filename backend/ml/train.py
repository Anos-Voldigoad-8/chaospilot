"""Train and evaluate the Phase 5 Isolation Forest on healthy windows only."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ml.data import load_dataset  # noqa: E402
from ml.evaluate import (  # noqa: E402
    choose_threshold,
    evaluate_windows,
    print_report,
    recommendations,
    write_json,
)
from ml.features import FEATURE_NAMES, WINDOW_SECONDS, Window, build_windows  # noqa: E402
from ml.plotting import plot_confusion_matrix  # noqa: E402
from ml.simulate import FAULTS  # noqa: E402

DEFAULT_DB = BACKEND_ROOT / "data" / "ml_dataset.db"
DEFAULT_MODEL = BACKEND_ROOT / "models" / "isolation_forest.joblib"
DEFAULT_METRICS = REPO_ROOT / "docs" / "model_metrics.json"
DEFAULT_CONFUSION = REPO_ROOT / "docs" / "confusion_matrix.png"

PURGE_SECONDS = WINDOW_SECONDS


@dataclass(frozen=True)
class Split:
    """Train/validation/test windows plus the experiment ids behind them."""

    train: list[Window]
    validation: list[Window]
    test: list[Window]
    train_experiments: list[int]
    validation_experiments: list[int]
    test_experiments: list[int]


def _experiment_split(runs: dict[int, dict[str, Any]]) -> tuple[set[int], set[int], set[int]]:
    """Hold out whole experiments, rotating target coverage across fault types."""
    grouped: dict[str, list[int]] = defaultdict(list)
    for experiment_id, run in runs.items():
        fault = str(run.get("fault") or "unknown")
        grouped[fault].append(experiment_id)

    train_ids: set[int] = set()
    validation_ids: set[int] = set()
    test_ids: set[int] = set()
    for fault, ids in sorted(grouped.items()):
        ids.sort()
        offset = FAULTS.index(fault) if fault in FAULTS else 0
        for position, experiment_id in enumerate(ids):
            slot = (position + offset) % 3
            if slot == 2:
                test_ids.add(experiment_id)
            elif slot == 1:
                validation_ids.add(experiment_id)
            else:
                train_ids.add(experiment_id)
    return train_ids, validation_ids, test_ids


def _split_healthy_windows(windows: list[Window]) -> tuple[list[Window], list[Window], list[Window]]:
    """Time split for the healthy-only recording, with a purge gap."""
    ordered = sorted(windows, key=lambda window: window.end)
    if not ordered:
        return [], [], []
    first = ordered[0].start
    span = max(ordered[-1].end - first, 1.0)
    train_end = first + span * 0.6
    validation_end = first + span * 0.8

    train = [window for window in ordered if window.end <= train_end]
    validation = [
        window
        for window in ordered
        if window.start > train_end and window.end <= validation_end
    ]
    test = [window for window in ordered if window.start > validation_end]
    return train, validation, test


def split_windows(windows: list[Window], runs: dict[int, dict[str, Any]]) -> Split:
    """Combine experiment hold-out and the healthy-only time split."""
    train_ids, validation_ids, test_ids = _experiment_split(runs)
    healthy_train, healthy_validation, healthy_test = _split_healthy_windows(
        [window for window in windows if window.experiment_id is None]
    )

    train = healthy_train + [
        window for window in windows if window.experiment_id in train_ids and window.label == 0
    ]
    validation = healthy_validation + [
        window for window in windows if window.experiment_id in validation_ids
    ]
    test = healthy_test + [
        window for window in windows if window.experiment_id in test_ids
    ]
    return Split(
        train=train,
        validation=validation,
        test=test,
        train_experiments=sorted(train_ids),
        validation_experiments=sorted(validation_ids),
        test_experiments=sorted(test_ids),
    )


def _matrix(windows: list[Window]) -> np.ndarray:
    return np.asarray([window.vector(FEATURE_NAMES) for window in windows], dtype=float)


def _calibration(model: IsolationForest, matrix: np.ndarray) -> tuple[float, float]:
    decisions = model.decision_function(matrix)
    center = float(np.quantile(decisions, 0.02))
    scale = float(np.quantile(decisions, 0.75) - np.quantile(decisions, 0.25))
    return center, max(scale / 1.349, 1e-6)


def _scores(model: IsolationForest, matrix: np.ndarray, center: float, scale: float) -> np.ndarray:
    decisions = model.decision_function(matrix)
    return 1.0 / (1.0 + np.exp((decisions - center) / scale))


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def train_from_database(
    database_path: str | Path = DEFAULT_DB,
    *,
    model_path: str | Path = DEFAULT_MODEL,
    metrics_path: str | Path = DEFAULT_METRICS,
    confusion_path: str | Path = DEFAULT_CONFUSION,
    trees: int = 200,
    contamination: float = 0.02,
    seed: int = 42,
) -> dict[str, Any]:
    """Fit, calibrate, evaluate and persist the model; return the metrics."""
    dataset = load_dataset(database_path)
    windows = build_windows(dataset.samples, dataset.runs)
    if not windows:
        raise ValueError(f"no labelled windows in {database_path}; run generate_dataset.py")

    split = split_windows(windows, dataset.runs)
    train_normal = [window for window in split.train if window.label == 0]
    if len(train_normal) < 30:
        raise ValueError(
            f"only {len(train_normal)} healthy training windows; record more healthy traffic"
        )
    if not any(window.label == 1 for window in split.test):
        raise ValueError("held-out split has no fault windows; add more experiments")

    train_matrix = _matrix(train_normal)
    model = IsolationForest(
        n_estimators=trees,
        contamination=contamination,
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(train_matrix)
    center, scale = _calibration(model, train_matrix)

    validation_scores = _scores(
        model, _matrix(split.validation), center, scale
    ) if split.validation else np.asarray([])
    validation_labels = [window.label for window in split.validation]
    threshold, validation_metrics = choose_threshold(
        validation_scores.tolist(), validation_labels
    )

    test_scores = _scores(model, _matrix(split.test), center, scale)
    test_metrics = evaluate_windows(split.test, test_scores.tolist(), threshold)
    validation_metrics = evaluate_windows(
        split.validation, validation_scores.tolist(), threshold
    )

    metadata = dataset.stats.get("metadata") or {}
    source = metadata.get("source", "unknown")
    payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": {
            "path": _display(Path(database_path)),
            "source": source,
            "samples": dataset.stats["samples"],
            "experiments": dataset.stats["experiments"],
            "fault_samples": dataset.stats["fault_samples"],
            "healthy_only_samples": dataset.stats["healthy_only_samples"],
            "windows": len(windows),
            "class_counts": {
                "normal": sum(1 for window in windows if window.label == 0),
                "fault": sum(1 for window in windows if window.label == 1),
            },
            "healthy_seconds": _optional_float(metadata.get("healthy_seconds")),
            "window_seconds": WINDOW_SECONDS,
            "feature_names": list(FEATURE_NAMES),
        },
        "model": {
            "type": "IsolationForest",
            "sklearn_version": sklearn.__version__,
            "params": {
                "n_estimators": trees,
                "contamination": contamination,
                "random_state": seed,
            },
            "calibration": {"center": round(center, 6), "scale": round(scale, 6)},
            "trained_windows": len(train_normal),
        },
        "split": {
            "train_windows": len(split.train),
            "validation_windows": len(split.validation),
            "test_windows": len(split.test),
            "train_fault_windows": sum(1 for window in split.train if window.label == 1),
            "validation_fault_windows": sum(
                1 for window in split.validation if window.label == 1
            ),
            "test_fault_windows": sum(1 for window in split.test if window.label == 1),
            "train_experiments": split.train_experiments,
            "validation_experiments": split.validation_experiments,
            "test_experiments": split.test_experiments,
        },
        "threshold": round(threshold, 4),
        "validation": validation_metrics,
        "test": test_metrics,
        "artifacts": {
            "model": _display(Path(model_path)),
            "metrics": _display(Path(metrics_path)),
            "confusion_matrix": _display(Path(confusion_path)),
        },
    }
    payload["recommendations"] = recommendations(
        test_metrics, payload["split"], dataset.stats
    )

    model_destination = Path(model_path)
    model_destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_names": list(FEATURE_NAMES),
            "window_seconds": WINDOW_SECONDS,
            "center": center,
            "scale": scale,
            "threshold": threshold,
            "trained_at": payload["generated_at"],
            "training": payload["split"],
        },
        model_destination,
    )
    plot_confusion_matrix(
        test_metrics["confusion_matrix"],
        confusion_path,
        threshold=threshold,
        f1=test_metrics["f1"],
    )
    write_json(metrics_path, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--confusion-matrix", type=Path, default=DEFAULT_CONFUSION)
    parser.add_argument("--trees", type=int, default=200)
    parser.add_argument("--contamination", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    try:
        payload = train_from_database(
            args.db,
            model_path=args.model,
            metrics_path=args.metrics,
            confusion_path=args.confusion_matrix,
            trees=args.trees,
            contamination=args.contamination,
            seed=args.seed,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"training failed: {exc}")
        return 1

    print_report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
