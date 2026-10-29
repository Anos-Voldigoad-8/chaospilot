"""Small WebSocket client for the ChaosPilot live stream.

Connects to ``/ws``, optionally starts an experiment through the REST API and
prints every event until the postmortem arrives. Exit code is 0 when a
postmortem was received.

Examples
--------
    python scripts/ws_client.py
    python scripts/ws_client.py --fault memory --target db
    python scripts/ws_client.py --no-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

import httpx
import websockets


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ws", default="ws://127.0.0.1:8090/ws")
    parser.add_argument("--api", default="http://127.0.0.1:8090")
    parser.add_argument(
        "--fault", choices=("kill", "latency", "memory"), default="latency"
    )
    parser.add_argument("--target", default="payments")
    parser.add_argument("--fixes", action="store_true")
    parser.add_argument(
        "--no-run", action="store_true", help="only observe, don't start an experiment"
    )
    parser.add_argument(
        "--timeout", type=float, default=150.0, help="overall seconds to wait"
    )
    return parser.parse_args(argv)


def format_event(event: dict[str, Any]) -> str:
    kind = event.get("type")
    if kind == "state":
        return (
            f"state    {event.get('service', '?'):<10} "
            f"{str(event.get('status', '?')):<5} "
            f"{event.get('latency_ms', 0):>8.1f} ms"
        )
    if kind == "metrics":
        return (
            f"metrics  gateway={event.get('gateway_latency', 0):>8.1f} ms  "
            f"error_rate={event.get('error_rate', 0):.3f}"
        )
    if kind == "score":
        return f"score    {event.get('value', 0):.1f}/100"
    if kind == "log":
        return f"log      [{event.get('level', 'info')}] {event.get('text', '')}"
    if kind == "postmortem":
        return f"postmortem\n{event.get('text', '')}"
    return json.dumps(event, sort_keys=True)


async def run(args: argparse.Namespace) -> int:
    async with websockets.connect(args.ws, open_timeout=10.0) as websocket:
        print(f"connected to {args.ws}")

        if not args.no_run:
            async with httpx.AsyncClient(base_url=args.api, timeout=15.0) as client:
                response = await client.post(
                    "/experiments/run",
                    json={
                        "fault": args.fault,
                        "target": args.target,
                        "fixes": args.fixes,
                    },
                )
                print(f"POST /experiments/run -> {response.status_code}")
                print(json.dumps(response.json(), indent=2))
                if response.status_code != 202:
                    return 1

        counts: dict[str, int] = {}
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                raw = await asyncio.wait_for(websocket.recv(), timeout=min(10.0, remaining))
            except TimeoutError:
                print("... still waiting for events")
                continue
            event = json.loads(raw)
            kind = str(event.get("type", "unknown"))
            counts[kind] = counts.get(kind, 0) + 1
            print(format_event(event))
            if kind == "postmortem":
                print(f"\nevent counts: {counts}")
                return 0

    print(f"\ntimed out without a postmortem; event counts: {counts}")
    return 1


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(run(parse_args(argv)))
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(f"cannot connect to the API: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
