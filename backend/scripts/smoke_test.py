"""Phase 2 end-to-end smoke test.

Starts the 1-second collector, records a baseline, injects ``--fault-ms`` of
latency into ``payments`` for ``--duration`` seconds, resets every fault and
records a recovery period. Gateway latency is read back from SQLite and printed
before, during and after the fault; the script exits non-zero unless the
during-window p50 jumps by at least ``--min-jump-ms``.

The sample stack must already be running (Docker Compose or local Uvicorn
processes). Nothing here needs Docker itself: latency is applied over HTTP.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import statistics
import sys
import time
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import httpx  # noqa: E402

from chaos.engine import ChaosEngine  # noqa: E402
from collector import Collector  # noqa: E402
from db import ChaosDatabase  # noqa: E402
from service_map import service_url  # noqa: E402

DEFAULT_DB = BACKEND_ROOT / "data" / "smoke.db"

LOGGER = logging.getLogger("smoke")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="sample stack host")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite file to use")
    parser.add_argument("--target", default="payments", help="service to slow down")
    parser.add_argument("--fault-ms", type=float, default=2000.0, help="injected latency")
    parser.add_argument("--duration", type=float, default=10.0, help="fault window seconds")
    parser.add_argument("--baseline", type=float, default=6.0, help="baseline seconds")
    parser.add_argument("--after", type=float, default=5.0, help="recovery seconds")
    parser.add_argument("--interval", type=float, default=1.0, help="collector interval")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds")
    parser.add_argument(
        "--min-jump-ms",
        type=float,
        default=800.0,
        help="required gateway p50 increase during the fault",
    )
    return parser.parse_args(argv)


def preflight(host: str, timeout: float) -> dict[str, Any]:
    """Fail early with a useful message when the stack is not reachable."""
    url = f"{service_url('gateway', host)}/health"
    try:
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
        health = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SystemExit(
            f"sample stack is not reachable at {url}: {exc}\n"
            "Start it with `docker compose up --build` in sample-stack/, "
            "or run the local Uvicorn helper first."
        ) from exc
    print(f"gateway healthy: {url} -> {health.get('status')} ({health.get('service')})")
    return health


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(row["latency_ms"]) for row in rows if row["latency_ms"] is not None]
    return {
        "samples": len(rows),
        "errors": sum(int(row["error"]) for row in rows),
        "labeled": sum(int(row["label"]) for row in rows),
        "p50_ms": round(statistics.median(latencies), 1) if latencies else None,
        "max_ms": round(max(latencies), 1) if latencies else None,
    }


def print_phase_table(title: str, phases: dict[str, dict[str, Any]]) -> None:
    print()
    print(title)
    print(f"{'phase':<9}{'samples':>9}{'errors':>8}{'label=1':>9}{'p50_ms':>10}{'max_ms':>10}")
    for name, stats in phases.items():
        p50 = stats["p50_ms"] if stats["p50_ms"] is not None else "-"
        peak = stats["max_ms"] if stats["max_ms"] is not None else "-"
        print(
            f"{name:<9}{stats['samples']:>9}{stats['errors']:>8}"
            f"{stats['labeled']:>9}{str(p50):>10}{str(peak):>10}"
        )


async def run(args: argparse.Namespace) -> int:
    preflight(args.host, args.timeout)

    database = ChaosDatabase(args.db)
    engine = ChaosEngine(host=args.host, http_timeout=args.timeout)
    collector = Collector(
        database,
        host=args.host,
        interval=args.interval,
        timeout=args.timeout,
    )

    collection_started = time.time()
    experiment_id: int | None = None
    fault_started: float | None = None
    fault_ended: float | None = None
    failure: Exception | None = None
    injection: dict[str, Any] | None = None
    recovery: dict[str, Any] | None = None

    await collector.start()
    try:
        print(f"collecting baseline for {args.baseline:.0f}s ...")
        await asyncio.sleep(args.baseline)

        fault_started = time.time()
        experiment_id = database.start_experiment(
            "latency", args.target, started=fault_started
        )
        injection = engine.latency(args.target, args.fault_ms)
        print(
            f"injected {args.fault_ms:.0f}ms on {args.target} "
            f"(experiment #{experiment_id}): ok={injection.get('ok')} "
            f"response={injection.get('response')}"
        )
        if not injection.get("ok"):
            raise RuntimeError(f"injection failed: {injection}")
        await asyncio.sleep(args.duration)
    except Exception as exc:  # noqa: BLE001 - reported below after cleanup
        failure = exc
    finally:
        if experiment_id is not None:
            recovery = engine.reset_all()
            fault_ended = time.time()
            database.end_experiment(experiment_id, ended=fault_ended)
            print(
                f"reset_all: ok={recovery.get('ok')} "
                f"duration={recovery.get('duration_ms')}ms"
            )

    if failure is None:
        print(f"collecting recovery for {args.after:.0f}s ...")
        await asyncio.sleep(args.after)
    await collector.stop()

    if failure is not None or fault_started is None or fault_ended is None:
        print(f"SMOKE TEST FAILED: {failure}")
        return 1

    after_end = fault_ended + args.after + 2.0
    gateway_phases = {
        "before": summarize(
            database.samples_between(collection_started, fault_started, service="gateway")
        ),
        "during": summarize(
            database.samples_between(fault_started, fault_ended, service="gateway")
        ),
        "after": summarize(
            database.samples_between(fault_ended, after_end, service="gateway")
        ),
    }
    target_phases = {
        "before": summarize(
            database.samples_between(collection_started, fault_started, service=args.target)
        ),
        "during": summarize(
            database.samples_between(fault_started, fault_ended, service=args.target)
        ),
        "after": summarize(
            database.samples_between(fault_ended, after_end, service=args.target)
        ),
    }

    print_phase_table("gateway /checkout end-to-end latency (ms)", gateway_phases)
    print_phase_table(
        f"{args.target} /health probe latency (ms) - target of the fault",
        target_phases,
    )
    print()
    print(f"database: {database.path} ({database.count_samples()} samples total)")
    print(f"experiments: {database.experiments()}")

    before = gateway_phases["before"]
    during = gateway_phases["during"]
    after = gateway_phases["after"]
    checks: list[tuple[bool, str]] = []

    if before["p50_ms"] is not None and during["p50_ms"] is not None:
        jump = round(float(during["p50_ms"]) - float(before["p50_ms"]), 1)
        checks.append(
            (
                jump >= args.min_jump_ms,
                f"gateway p50 jumped {jump:+.1f}ms "
                f"(required >= {args.min_jump_ms:.0f}ms)",
            )
        )
    else:
        checks.append((False, "not enough gateway samples before/during the fault"))

    checks.append((during["samples"] >= 3, f"during-window samples: {during['samples']}"))
    checks.append((during["labeled"] == during["samples"], "during labels are all 1"))
    checks.append((before["labeled"] == 0, "before labels are all 0"))
    checks.append((after["labeled"] == 0, "after labels are all 0"))
    checks.append((during["errors"] == 0, "no failed checks during the fault"))
    if during["p50_ms"] is not None and after["p50_ms"] is not None:
        checks.append(
            (
                float(after["p50_ms"]) < float(during["p50_ms"]) - 500,
                f"gateway p50 recovered to {after['p50_ms']}ms",
            )
        )
    if target_phases["during"]["p50_ms"] is not None:
        checks.append(
            (
                float(target_phases["during"]["p50_ms"]) >= args.fault_ms - 100,
                f"{args.target} health probe saw >= {args.fault_ms - 100:.0f}ms",
            )
        )

    print()
    for ok, description in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {description}")

    if all(ok for ok, _ in checks):
        print("\nSMOKE TEST PASSED: visible latency jump during the fault window.")
        return 0
    print("\nSMOKE TEST FAILED.")
    return 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # The collector logs every HTTP probe at INFO; keep the smoke output readable.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
