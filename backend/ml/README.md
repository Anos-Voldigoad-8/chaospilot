# Anomaly model pipeline

Phase 5 pipeline for labelled chaos data, sliding-window features and the
Isolation Forest used by the detector. It is independent of the older
`core/ml` scaffold and runs from `backend/`.

## Quickstart

```bash
cd backend

# 24 experiments (all faults and targets) + 10 minutes of healthy traffic.
# --source auto uses the Docker stack when it is healthy and otherwise falls
# back to the deterministic simulator.
python -m ml.scripts.generate_dataset --source auto

# Fit on healthy windows, tune the threshold, evaluate on held-out experiments.
python -m ml.train
```

Expected runtime: seconds with the simulator; roughly 20 minutes against the
stack (24 x 20s phases plus 10 minutes of healthy recording).

## Dataset

`ml/scripts/generate_dataset.py` writes to `backend/data/ml_dataset.db` by
default (git-ignored). It always starts from a fresh database.

- 24 experiments: the full 3 faults (`kill`, `latency`, `memory`) x 6 targets
  matrix, plus six replicates.
- Phase windows: 5s baseline, 10s fault, 5s recovery, sampled once per second.
- 10 minutes of healthy-only traffic with no experiment id. With `--source
  stack` this is recorded in real time; the simulator generates the same ten
  simulated minutes instantly.
- Rows keep the raw phase label, while the feature builder assigns the
  service-level label: only the target and its transitive callers are positive
  during the fault. Unaffected services in the same wall-clock window are hard
  negatives, which keeps precision meaningful.

`--source stack` runs the real `ExperimentRunner` and collector;
`--source simulated` uses the topology-aware simulator in `ml/simulate.py`.
The generator records its source, seed, plan and phase lengths in the
`ml_meta` table so a metrics file can state where the data came from.

## Features

`ml/features.py` builds a five-second window for each service and the same
window for its direct dependencies. The dependency block is aggregated, so the
vector is fixed-length regardless of the number of callees.

| Feature | Meaning |
| --- | --- |
| `latency_mean`, `latency_max` | latency over the window |
| `error_rate` | fraction of failed probes |
| `up_ratio` | fraction of successful probes |
| `latency_slope` | least-squares slope in ms/s |
| `dep_latency_mean`, `dep_latency_max` | dependency latency |
| `dep_error_rate` | worst dependency error rate |
| `dep_up_ratio` | worst dependency availability |
| `dep_latency_slope` | mean dependency slope |

Recovery windows and windows that straddle the fault onset are excluded from
both classes. The model is trained only on label `0` (healthy) windows.

## Splits and evaluation

- Whole experiments are held out, grouped by fault and rotated so the test set
  covers different targets. Experiments are never shared between train,
  validation and test.
- Healthy-only windows are split 60/20/20 by time with a five-second purge gap.
- The Isolation Forest is fitted on training healthy windows only.
- Raw `decision_function` scores are calibrated to 0-1 with a robust
  logistic mapping; the threshold is chosen on the validation set by F1.
- Test metrics include precision, recall, F1, accuracy, specificity, confusion
  matrix, score quantiles and per-fault recall.

## Artifacts

| Path | Notes |
| --- | --- |
| `backend/models/isolation_forest.joblib` | model + calibration + threshold (git-ignored) |
| `docs/model_metrics.json` | dataset, split, threshold and metrics |
| `docs/confusion_matrix.png` | held-out test confusion matrix |

## Detector

```python
from ml.detector import AnomalyDetector
from ml.features import Window

detector = AnomalyDetector.load()
score = detector.score(window)           # Window, mapping or feature sequence
if detector.is_anomaly(window):
    ...
```

`score()` returns 0-1; values above `detector.threshold` are anomalies.

## Limitations

- The simulator produces cleaner separations than real containers. Use
  `--source stack` before trusting absolute scores.
- Adjacent one-second windows overlap, so the point metrics are optimistic;
  evaluation on non-overlapping windows or confidence intervals is a useful
  next step.
- The sample stack exposes only health/checkout latency and error, not error
  classes, restarts or resource pressure. Those signals would improve subtle
  memory faults.
