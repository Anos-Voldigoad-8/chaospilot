"""Evaluation helpers: metrics, threshold tuning and the confusion matrix PNG."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from ml.features import FEATURE_NAMES, Window


def binary_metrics(labels: Sequence[int], predictions: Sequence[int]) -> dict[str, Any]:
    """Precision, recall, F1 and the raw confusion counts."""
    true_positive = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 1 and p == 1)
    false_positive = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 0 and p == 1)
    false_negative = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 1 and p == 0)
    true_negative = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 0 and p == 0)

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    total = true_positive + false_positive + false_negative + true_negative
    specificity = (
        true_negative / (true_negative + false_positive)
        if true_negative + false_positive
        else 0.0
    )
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round((true_positive + true_negative) / total, 4) if total else 0.0,
        "specificity": round(specificity, 4),
        "support": {
            "total": total,
            "normal": true_negative + false_positive,
            "fault": true_positive + false_negative,
        },
        "confusion_matrix": [
            [true_negative, false_positive],
            [false_negative, true_positive],
        ],
    }


def choose_threshold(scores: Sequence[float], labels: Sequence[int]) -> tuple[float, dict[str, Any]]:
    """Pick the 0-1 threshold with the best validation F1."""
    values = np.asarray(scores, dtype=float)
    truth = np.asarray(labels, dtype=int)
    if len(values) == 0 or truth.min() == truth.max():
        return 0.5, binary_metrics(truth.tolist(), (values >= 0.5).astype(int).tolist())

    candidates = np.unique(
        np.clip(np.quantile(values, np.linspace(0.05, 0.995, 200)), 0.01, 0.999)
    )
    best_threshold = 0.5
    best_metrics = binary_metrics(truth.tolist(), (values >= 0.5).astype(int).tolist())
    best_rank = (best_metrics["f1"], best_metrics["recall"], best_metrics["precision"], 0.0)
    for threshold in candidates:
        metrics = binary_metrics(
            truth.tolist(), (values >= threshold).astype(int).tolist()
        )
        rank = (
            metrics["f1"],
            metrics["recall"],
            metrics["precision"],
            -abs(float(threshold) - 0.5),
        )
        if rank > best_rank:
            best_threshold = float(threshold)
            best_metrics = metrics
            best_rank = rank
    return best_threshold, best_metrics


def score_summary(values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return {"count": 0, "mean": 0.0, "p05": 0.0, "p50": 0.0, "p95": 0.0}
    return {
        "count": int(array.size),
        "mean": round(float(array.mean()), 4),
        "p05": round(float(np.quantile(array, 0.05)), 4),
        "p50": round(float(np.quantile(array, 0.50)), 4),
        "p95": round(float(np.quantile(array, 0.95)), 4),
    }


def evaluate_windows(
    windows: Sequence[Window],
    scores: Sequence[float],
    threshold: float,
) -> dict[str, Any]:
    """Build the full test/validation metrics block."""
    labels = [window.label for window in windows]
    predictions = [1 if score >= threshold else 0 for score in scores]
    block = binary_metrics(labels, predictions)
    block["score_stats"] = {
        "normal": score_summary([s for s, y in zip(scores, labels, strict=True) if y == 0]),
        "fault": score_summary([s for s, y in zip(scores, labels, strict=True) if y == 1]),
    }

    per_fault: dict[str, dict[str, Any]] = {}
    for fault in sorted({window.fault for window in windows if window.fault}):
        indices = [
            index
            for index, window in enumerate(windows)
            if window.fault == fault and window.label == 1
        ]
        if not indices:
            continue
        caught = sum(1 for index in indices if predictions[index] == 1)
        per_fault[fault] = {
            "fault_windows": len(indices),
            "detected": caught,
            "recall": round(caught / len(indices), 4),
        }
    block["per_fault"] = per_fault
    return block


def recommendations(
    test: Mapping[str, Any],
    split: Mapping[str, Any],
    dataset_stats: Mapping[str, Any],
) -> list[str]:
    """Short, concrete next steps based on the observed metrics."""
    tips: list[str] = []
    metadata = dataset_stats.get("metadata") or {}

    if metadata.get("source") == "simulated":
        tips.append(
            "This run uses simulated telemetry. Re-generate with --source stack on the "
            "real Compose stack before trusting the absolute scores; synthetic faults "
            "are cleaner than container-level failures."
        )
    if test["recall"] < 0.8:
        tips.append(
            "Recall is below 0.8. Add more fault experiments (especially kill/memory on "
            "quiet targets such as cache and db), include longer fault windows, or lower "
            "the threshold. Check per-fault recall to see which fault type is missed."
        )
    if test["precision"] < 0.8:
        tips.append(
            "Precision is below 0.8. Record more healthy traffic, keep the purge gap "
            "between train and test windows, and exclude recovery/ramp windows (already "
            "done here). A higher threshold trades recall for fewer false alarms."
        )
    if test["f1"] < 0.8:
        tips.append(
            "F1 is below 0.8. Try a slightly longer window (8-10s), add a short rolling "
            "history of the previous window's features, or model each service separately "
            "so quiet services like db are not compared with gateway's baseline."
        )
    weak_faults = [
        fault
        for fault, result in (test.get("per_fault") or {}).items()
        if result["recall"] < 0.7
    ]
    if weak_faults:
        tips.append(
            "Weak recall for: "
            + ", ".join(weak_faults)
            + ". Increase the fault intensity or duration for those runs, or add "
            "fault-specific signals (container restarts, error classes, queue depth)."
        )
    if split.get("test_fault_windows", 0) < 100:
        tips.append(
            "The held-out fault set is small. Add replicates so precision/recall do not "
            "swing on a handful of windows."
        )

    tips.append(
        "Evaluate on non-overlapping windows (or report confidence intervals): adjacent "
        "1-second windows share samples, so the point estimates are optimistic."
    )
    if not tips:
        tips.append(
            "Metrics look healthy. Validate on a fresh set of real experiments and monitor "
            "false-positive rate during long healthy periods before enabling alerts."
        )
    return tips


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def print_report(payload: Mapping[str, Any]) -> None:
    """Print a terminal-friendly summary of the metrics payload."""
    test = payload["test"]
    validation = payload["validation"]
    split = payload["split"]
    print("\n=== ChaosPilot anomaly model ===")
    print(
        f"Dataset: {payload['dataset']['samples']} samples, "
        f"{payload['dataset']['experiments']} experiments, "
        f"{payload['dataset']['windows']} windows "
        f"({payload['dataset']['class_counts']['normal']} normal / "
        f"{payload['dataset']['class_counts']['fault']} fault)"
    )
    if payload["dataset"].get("source"):
        print(f"Source: {payload['dataset']['source']}")
    print(
        f"Split: train={split['train_windows']} val={split['validation_windows']} "
        f"test={split['test_windows']} windows"
    )
    print(
        f"Threshold: {payload['threshold']:.3f} "
        f"(validation F1 {validation['f1']:.3f})"
    )
    matrix = test["confusion_matrix"]
    print("\nHeld-out test set")
    print(f"  confusion matrix [[TN, FP], [FN, TP]]: {matrix}")
    print(
        f"  precision {test['precision']:.3f} | recall {test['recall']:.3f} | "
        f"F1 {test['f1']:.3f} | accuracy {test['accuracy']:.3f}"
    )
    print(
        f"  normal score p50/p95: {test['score_stats']['normal']['p50']:.3f}/"
        f"{test['score_stats']['normal']['p95']:.3f} | "
        f"fault score p50/p95: {test['score_stats']['fault']['p50']:.3f}/"
        f"{test['score_stats']['fault']['p95']:.3f}"
    )
    if test.get("per_fault"):
        print("  recall by fault:")
        for fault, result in test["per_fault"].items():
            print(
                f"    {fault:<8} {result['recall']:.3f} "
                f"({result['detected']}/{result['fault_windows']})"
            )

    print("\nHow to improve weak results")
    for tip in payload["recommendations"]:
        print(f"  - {tip}")
    print(f"\nMetrics JSON: {payload['artifacts']['metrics']}")
    print(f"Confusion matrix: {payload['artifacts']['confusion_matrix']}")
    print(f"Model bundle: {payload['artifacts']['model']}")


def feature_schema() -> list[str]:
    """Stable feature order used by the model and the detector."""
    return list(FEATURE_NAMES)
