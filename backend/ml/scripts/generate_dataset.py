"""Generate a labelled chaos dataset for the Phase 5 anomaly model.

Two sources are supported:

``stack``
    Runs real 5s baseline / 10s fault / 5s recovery experiments against the
    Docker Compose sample stack and records 10 minutes of healthy traffic.

``simulated``
    Uses the same topology and phase labels without Docker. This is the default
    fallback when the stack is unreachable, so the pipeline can be reproduced
    on any laptop.

Run from ``backend/``::

    python -m ml.scripts.generate_dataset --source auto
"""

from __future__ import annotations

# Imports follow the sys.path bootstrap below so the script also runs directly.
# ruff: noqa: E402, I001

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api_config import ApiSettings  # noqa: E402
from collector import Collector  # noqa: E402
from db import ChaosDatabase  # noqa: E402
from experiments import ExperimentRunner  # noqa: E402
from ml.data import (
    load_dataset,  # noqa: E402
    write_metadata,  # noqa: E402
)
from ml.features import build_windows  # noqa: E402
from ml.simulate import (  # noqa: E402
    BASELINE_SECONDS,
    FAULT_SECONDS,
    RECOVERY_SECONDS,
    build_experiment_plan,
    write_simulated_dataset,
)
from stack import StackController  # noqa: E402
from ws import EventHub  # noqa: E402

DEFAULT_DB = BACKEND_ROOT / "data" / "ml_dataset.db"


def _reset_database(path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def _plan_summary(plan: list[tuple[str, str]]) -> None:
    counts: dict[str, int] = {}
    for fault, _ in plan:
        counts[fault] = counts.get(fault, 0) + 1
    print(f"Plan: {len(plan)} experiments " + ", ".join(
        f"{fault}={count}" for fault, count in sorted(counts.items())
    ))
    targets = sorted({target for _, target in plan})
    print(f"Targets covered: {', '.join(targets)}")


async def _probe_stack(host: str, timeout: float) -> tuple[bool, list[str]]:
    stack = StackController(host=host)
    health = await stack.wait_healthy(timeout=timeout)
    return bool(health.get("ok")), list(health.get("unreachable") or [])


async def _record_healthy(
    database: ChaosDatabase, settings: ApiSettings, seconds: float
) -> None:
    if seconds <= 0:
        return
    print(f"Recording {seconds / 60:.1f} minutes of healthy-only traffic...")
    collector = Collector(
        database, host=settings.host, interval=settings.collector_interval
    )
    await collector.start()
    try:
        remaining = seconds
        while remaining > 0:
            step = min(30.0, remaining)
            await asyncio.sleep(step)
            remaining -= step
            if remaining > 0:
                print(f"  healthy traffic: {seconds - remaining:.0f}/{seconds:.0f}s")
    finally:
        await collector.stop()


async def _run_stack(
    database_path: Path,
    plan: list[tuple[str, str]],
    *,
    host: str,
    healthy_seconds: float,
    baseline_seconds: float,
    fault_seconds: float,
    recovery_seconds: float,
    health_timeout: float,
) -> int:
    settings = ApiSettings(
        db_path=database_path,
        host=host,
        baseline_seconds=baseline_seconds,
        fault_seconds=fault_seconds,
        recovery_seconds=recovery_seconds,
    )
    stack = StackController(directory=settings.stack_directory, host=host)
    health = await stack.wait_healthy(timeout=health_timeout)
    if not health.get("ok"):
        print(f"sample stack is not healthy: {health.get('unreachable')}")
        return 1

    database = ChaosDatabase(database_path)
    await _record_healthy(database, settings, healthy_seconds)

    runner = ExperimentRunner(database, EventHub(), settings=settings, stack=stack)
    failures = 0
    try:
        for index, (fault, target) in enumerate(plan, start=1):
            detail = await runner.start(fault=fault, target=target, fixes=False)
            experiment_id = int(detail["id"])
            print(
                f"[{index:02d}/{len(plan)}] experiment #{experiment_id}: "
                f"{fault} -> {target}"
            )
            while runner.running:
                await asyncio.sleep(0.5)
            result = database.run_detail(experiment_id) or {}
            if result.get("status") != "completed":
                failures += 1
                print(f"  status={result.get('status')} error={result.get('error')}")
            await asyncio.sleep(1.0)
    finally:
        await runner.shutdown()

    write_metadata(
        database,
        {
            "source": "stack",
            "experiments": len(plan),
            "healthy_seconds": healthy_seconds,
            "baseline_seconds": baseline_seconds,
            "fault_seconds": fault_seconds,
            "recovery_seconds": recovery_seconds,
            "window_seconds": 5.0,
            "plan": json.dumps(plan),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )
    return 0 if failures == 0 else 2


def _report(database_path: Path) -> None:
    dataset = load_dataset(database_path)
    windows = build_windows(dataset.samples, dataset.runs)
    healthy = sum(1 for window in windows if window.label == 0)
    fault = sum(1 for window in windows if window.label == 1)
    print("Dataset summary")
    print(f"  path: {database_path}")
    print(f"  samples: {dataset.stats['samples']}")
    print(f"  experiments: {dataset.stats['experiments']}")
    print(f"  fault samples: {dataset.stats['fault_samples']}")
    print(f"  healthy-only samples: {dataset.stats['healthy_only_samples']}")
    print(f"  windows: {len(windows)} (healthy={healthy}, fault={fault})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("auto", "stack", "simulated"), default="auto")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--experiments", type=int, default=24)
    parser.add_argument("--healthy-minutes", type=float, default=10.0)
    parser.add_argument("--baseline", type=float, default=BASELINE_SECONDS)
    parser.add_argument("--fault", type=float, default=FAULT_SECONDS)
    parser.add_argument("--recovery", type=float, default=RECOVERY_SECONDS)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--health-timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    if args.experiments < 20:
        parser.error("--experiments must be at least 20 to cover the matrix")
    if args.healthy_minutes < 0:
        parser.error("--healthy-minutes must not be negative")

    plan = build_experiment_plan(args.experiments)
    _plan_summary(plan)
    _reset_database(args.db)

    source = args.source
    if source == "auto":
        ok, unreachable = asyncio.run(_probe_stack(args.host, args.health_timeout))
        source = "stack" if ok else "simulated"
        reason = "stack healthy" if ok else f"stack unreachable: {unreachable}"
        print(f"auto source: {source} ({reason})")

    healthy_seconds = args.healthy_minutes * 60.0
    if source == "stack":
        code = asyncio.run(
            _run_stack(
                args.db,
                plan,
                host=args.host,
                healthy_seconds=healthy_seconds,
                baseline_seconds=args.baseline,
                fault_seconds=args.fault,
                recovery_seconds=args.recovery,
                health_timeout=max(args.health_timeout, 90.0),
            )
        )
        if code != 0:
            return code
    else:
        started = time.perf_counter()
        result = write_simulated_dataset(
            args.db,
            experiments=args.experiments,
            healthy_seconds=healthy_seconds,
            baseline_seconds=args.baseline,
            fault_seconds=args.fault,
            recovery_seconds=args.recovery,
            seed=args.seed,
        )
        print(
            f"Simulated {result.experiments} experiments in "
            f"{time.perf_counter() - started:.2f}s (seed={args.seed})."
        )

    _report(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
