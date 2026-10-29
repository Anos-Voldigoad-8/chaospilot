"""Restart the Docker Compose sample stack in a chosen resilience mode."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

import httpx

from service_map import ALL_SERVICES, service_url

LOGGER = logging.getLogger(__name__)

SAMPLE_STACK_DIR = Path(__file__).resolve().parent.parent / "sample-stack"


class StackController:
    """Owns stack restarts and health checks (Docker Compose by default)."""

    def __init__(
        self,
        *,
        directory: Path = SAMPLE_STACK_DIR,
        host: str = "127.0.0.1",
        restart_timeout: float = 180.0,
        health_timeout: float = 90.0,
    ) -> None:
        self.directory = directory
        self.host = host
        self.restart_timeout = restart_timeout
        self.health_timeout = health_timeout

    async def restart(self, *, resilient: bool) -> dict[str, Any]:
        """Recreate the stack with ``RESILIENT=true|false`` in its environment."""
        docker = shutil.which("docker")
        if docker is None:
            return {
                "ok": False,
                "resilient": resilient,
                "error": "docker CLI not found; cannot restart the sample stack",
            }

        environment = os.environ.copy()
        environment["RESILIENT"] = "true" if resilient else "false"
        command = [docker, "compose", "up", "-d", "--force-recreate"]
        started = time.perf_counter()
        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self.directory),
                env=environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output, _ = await asyncio.wait_for(
                process.communicate(), timeout=self.restart_timeout
            )
        except TimeoutError:
            if process is not None:
                process.kill()
                await process.wait()
            return {
                "ok": False,
                "resilient": resilient,
                "error": f"docker compose restart timed out after {self.restart_timeout}s",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except OSError as exc:
            return {
                "ok": False,
                "resilient": resilient,
                "error": f"{type(exc).__name__}: {exc}",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }

        text = (output or b"").decode(errors="replace").strip()
        if process.returncode != 0:
            LOGGER.warning("docker compose restart failed: %s", text[-1000:])
        return {
            "ok": process.returncode == 0,
            "resilient": resilient,
            "command": " ".join(command),
            "returncode": process.returncode,
            "output": text[-2_000:],
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    async def wait_healthy(self, *, timeout: float | None = None) -> dict[str, Any]:
        """Poll every service's ``/health`` until all answer or time expires."""
        deadline = time.monotonic() + (self.health_timeout if timeout is None else timeout)
        pending = set(ALL_SERVICES)
        checked: dict[str, bool] = {}

        while pending and time.monotonic() < deadline:
            async with httpx.AsyncClient(timeout=2.0) as client:
                results = await asyncio.gather(
                    *(self._check(client, service) for service in sorted(pending))
                )
            for service, healthy in results:
                checked[service] = healthy
                if healthy:
                    pending.discard(service)
            if pending:
                await asyncio.sleep(0.5)

        return {
            "ok": not pending,
            "unreachable": sorted(pending),
            "checked": checked,
        }

    async def _check(self, client: httpx.AsyncClient, service: str) -> tuple[str, bool]:
        try:
            response = await client.get(f"{service_url(service, self.host)}/health")
            return service, response.status_code == 200
        except httpx.HTTPError:
            return service, False
