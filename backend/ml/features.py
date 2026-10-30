"""Sliding-window features for the Phase 5 anomaly model.

Every window covers five seconds of one service, plus the same five seconds of
its direct dependencies (as declared in :mod:`topology`). The dependency block
is aggregated so a service has a fixed-length vector no matter how many callees
it has: mean latency, worst latency, worst error rate, worst availability and
mean latency slope.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from topology import DEPENDENCIES

WINDOW_SECONDS = 5.0
MIN_WINDOW_SAMPLES = 3

BASE_FEATURE_NAMES: tuple[str, ...] = (
    "latency_mean",
    "latency_max",
    "error_rate",
    "up_ratio",
    "latency_slope",
)
DEPENDENCY_FEATURE_NAMES: tuple[str, ...] = (
    "dep_latency_mean",
    "dep_latency_max",
    "dep_error_rate",
    "dep_up_ratio",
    "dep_latency_slope",
)
FEATURE_NAMES: tuple[str, ...] = BASE_FEATURE_NAMES + DEPENDENCY_FEATURE_NAMES

SampleRow = Mapping[str, Any]
RunRow = Mapping[str, Any]

#: Downstream services for each caller, derived once from the static topology.
DEPENDENCIES_BY_SERVICE: dict[str, tuple[str, ...]] = {
    source: tuple(target for origin, target in DEPENDENCIES if origin == source)
    for source in {edge[0] for edge in DEPENDENCIES}
}

#: Direct callers of each service, used to decide which services a fault reaches.
CALLERS_BY_SERVICE: dict[str, tuple[str, ...]] = {
    target: tuple(source for source, dependency in DEPENDENCIES if dependency == target)
    for target in {edge[1] for edge in DEPENDENCIES}
}


def affected_services(target: str) -> frozenset[str]:
    """Target plus every transitive caller: the services a fault can degrade."""
    affected = {target}
    frontier = [target]
    while frontier:
        service = frontier.pop()
        for caller in CALLERS_BY_SERVICE.get(service, ()):
            if caller not in affected:
                affected.add(caller)
                frontier.append(caller)
    return frozenset(affected)


@dataclass(frozen=True)
class Window:
    """One labelled feature vector for a service and time span."""

    service: str
    start: float
    end: float
    label: int
    phase: str
    experiment_id: int | None
    fault: str | None
    target: str | None
    features: dict[str, float] = field(default_factory=dict)

    def vector(self, names: Iterable[str] = FEATURE_NAMES) -> list[float]:
        """Return the numeric vector in a stable feature order."""
        return [float(self.features[name]) for name in names]


def _latency(row: SampleRow) -> float:
    value = row.get("latency_ms")
    return float(value) if value is not None else 0.0


def _slope(rows: list[SampleRow]) -> float:
    """Least-squares latency slope in milliseconds per second."""
    if len(rows) < 2:
        return 0.0
    origin = float(rows[0]["ts"])
    xs = [float(row["ts"]) - origin for row in rows]
    ys = [_latency(row) for row in rows]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator <= 0.0:
        return 0.0
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    return numerator / denominator


def base_features(rows: list[SampleRow]) -> dict[str, float]:
    """Extract the five per-service features from one window of samples."""
    if not rows:
        return {
            "latency_mean": 0.0,
            "latency_max": 0.0,
            "error_rate": 0.0,
            "up_ratio": 1.0,
            "latency_slope": 0.0,
        }
    latencies = [_latency(row) for row in rows]
    return {
        "latency_mean": sum(latencies) / len(latencies),
        "latency_max": max(latencies),
        "error_rate": sum(1 for row in rows if row.get("error")) / len(rows),
        "up_ratio": sum(1 for row in rows if row.get("up")) / len(rows),
        "latency_slope": _slope(rows),
    }


def _dependency_features(
    service: str,
    window_start: float,
    window_end: float,
    series: Mapping[str, list[SampleRow]],
    times: Mapping[str, list[float]],
) -> dict[str, float]:
    collected: list[dict[str, float]] = []
    for dependency in DEPENDENCIES_BY_SERVICE.get(service, ()):
        dependency_rows = series.get(dependency)
        if not dependency_rows:
            continue
        lo = bisect_left(times[dependency], window_start)
        hi = bisect_right(times[dependency], window_end)
        if hi - lo < MIN_WINDOW_SAMPLES:
            continue
        collected.append(base_features(dependency_rows[lo:hi]))

    if not collected:
        return {
            "dep_latency_mean": 0.0,
            "dep_latency_max": 0.0,
            "dep_error_rate": 0.0,
            "dep_up_ratio": 1.0,
            "dep_latency_slope": 0.0,
        }

    return {
        "dep_latency_mean": sum(item["latency_mean"] for item in collected) / len(collected),
        "dep_latency_max": max(item["latency_max"] for item in collected),
        "dep_error_rate": max(item["error_rate"] for item in collected),
        "dep_up_ratio": min(item["up_ratio"] for item in collected),
        "dep_latency_slope": sum(item["latency_slope"] for item in collected) / len(collected),
    }


def _label_window(
    rows: list[SampleRow],
    run: RunRow | None,
    end: float,
    service: str,
    window_seconds: float = WINDOW_SECONDS,
) -> tuple[str, int | None]:
    """Classify a window by experiment phase; ``None`` means ambiguous.

    A fault only degrades its target and the callers upstream of it. Windows for
    unrelated services during the fault window stay normal (hard negatives)
    instead of being counted as false negatives of the detector.
    """
    if run is None:
        return "healthy", 0

    target = str(run.get("target") or "")
    affected = affected_services(target) if target else frozenset()
    labels = [int(row.get("label") or 0) for row in rows]
    fault_fraction = sum(labels) / len(labels) if labels else 0.0
    fault_started = run.get("fault_started")
    fault_ended = run.get("fault_ended")
    recovery_end = run.get("recovery_end")

    def during_fault() -> tuple[str, int]:
        if service in affected or not affected:
            return "fault", 1
        return "fault-unaffected", 0

    if fault_started is None:
        # Older rows only have a label flag; trust the majority vote.
        if fault_fraction >= 0.5:
            return during_fault()
        if fault_fraction == 0.0:
            return "baseline", 0
        return "ramp", None

    if end < float(fault_started):
        return "baseline", 0
    if fault_ended is not None and end <= float(fault_ended):
        if fault_fraction >= 0.5:
            return during_fault()
        return "ramp", None
    if recovery_end is not None and end < float(recovery_end) + window_seconds:
        return "recovery", None
    return "post", 0


def build_windows(
    samples: Iterable[SampleRow],
    runs: Mapping[int, RunRow],
    *,
    window_seconds: float = WINDOW_SECONDS,
    min_samples: int = MIN_WINDOW_SAMPLES,
) -> list[Window]:
    """Build labelled sliding windows for every service in ``samples``.

    Windows during recovery are skipped: they are neither healthy reference
    data nor clean fault examples. Windows that straddle the start of a fault
    are kept only when at least half of their samples are fault samples.
    """
    series: dict[str, list[SampleRow]] = defaultdict(list)
    for row in samples:
        series[str(row["service"])].append(row)

    times: dict[str, list[float]] = {}
    for service, rows in series.items():
        rows.sort(key=lambda row: float(row["ts"]))
        times[service] = [float(row["ts"]) for row in rows]

    windows: list[Window] = []
    for service, rows in series.items():
        service_times = times[service]
        for index, row in enumerate(rows):
            end = float(row["ts"])
            start = end - window_seconds
            lo = bisect_left(service_times, start)
            hi = index + 1
            window_rows = rows[lo:hi]
            if hi - lo < min_samples:
                continue

            experiment_id = row.get("experiment_id")
            experiment_id = int(experiment_id) if experiment_id is not None else None
            run = runs.get(experiment_id) if experiment_id is not None else None
            phase, label = _label_window(
                window_rows, run, end, service, window_seconds
            )
            if label is None:
                continue

            features = base_features(window_rows)
            features.update(
                _dependency_features(service, start, end, series, times)
            )
            windows.append(
                Window(
                    service=service,
                    start=start,
                    end=end,
                    label=label,
                    phase=phase,
                    experiment_id=experiment_id,
                    fault=str(run["fault"]) if run and run.get("fault") else None,
                    target=str(run["target"]) if run and run.get("target") else None,
                    features=features,
                )
            )

    windows.sort(key=lambda window: (window.end, window.service))
    return windows
