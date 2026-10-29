"""Chaos engine for the sample stack.

Latency and memory faults are applied through each service's ``/_chaos``
endpoints. Container kill/restore uses the Docker SDK for Python and is only
required for crash experiments; the HTTP faults work without Docker.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from service_map import ALL_SERVICES, SERVICE_PORTS, service_url

LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = os.getenv("SAMPLE_STACK_HOST", "127.0.0.1")
DEFAULT_PROJECT = os.getenv("COMPOSE_PROJECT_NAME", "chaospilot")


class ChaosEngine:
    """Applies and clears chaos faults, returning a result dict every time."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        project: str = DEFAULT_PROJECT,
        *,
        http_timeout: float = 5.0,
    ) -> None:
        self.host = host
        self.project = project
        self.http_timeout = http_timeout
        self._docker_client: Any | None = None

    # ------------------------------------------------------------------
    # Docker-backed faults
    # ------------------------------------------------------------------
    def _docker(self) -> Any:
        if self._docker_client is None:
            import docker

            self._docker_client = docker.from_env()
        return self._docker_client

    def _container(self, service: str) -> Any:
        client = self._docker()
        try:
            return client.containers.get(f"{self.project}-{service}")
        except Exception as exc:
            containers = client.containers.list(
                all=True,
                filters={
                    "label": [
                        f"com.docker.compose.project={self.project}",
                        f"com.docker.compose.service={service}",
                    ]
                },
            )
            if not containers:
                raise RuntimeError(
                    f"no container for service {service!r} in project {self.project!r}"
                ) from exc
            return containers[0]

    def kill(self, service: str) -> dict[str, Any]:
        """Stop the service container."""
        started = time.perf_counter()
        if service not in SERVICE_PORTS:
            return self._invalid(service, "kill", started)
        try:
            container = self._container(service)
            container.stop(timeout=5)
            return {
                "action": "kill",
                "service": service,
                "ok": True,
                "container": container.name,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except Exception as exc:
            LOGGER.warning("kill(%s) failed: %s", service, exc)
            return {
                "action": "kill",
                "service": service,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }

    def restore(self, service: str) -> dict[str, Any]:
        """Start the service container again."""
        started = time.perf_counter()
        if service not in SERVICE_PORTS:
            return self._invalid(service, "restore", started)
        try:
            container = self._container(service)
            container.start()
            return {
                "action": "restore",
                "service": service,
                "ok": True,
                "container": container.name,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except Exception as exc:
            LOGGER.warning("restore(%s) failed: %s", service, exc)
            return {
                "action": "restore",
                "service": service,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }

    # ------------------------------------------------------------------
    # HTTP-backed faults
    # ------------------------------------------------------------------
    def _post_chaos(
        self, action: str, service: str, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        started = time.perf_counter()
        if service not in SERVICE_PORTS:
            return self._invalid(service, action, started)
        url = f"{service_url(service, self.host)}{path}"
        try:
            response = httpx.post(url, json=payload, timeout=self.http_timeout)
            body: Any
            try:
                body = response.json()
            except ValueError:
                body = response.text[:300]
            return {
                "action": action,
                "service": service,
                "ok": response.status_code == 200,
                "status_code": response.status_code,
                "url": url,
                "response": body,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except httpx.HTTPError as exc:
            return {
                "action": action,
                "service": service,
                "ok": False,
                "url": url,
                "error": f"{type(exc).__name__}: {exc}",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }

    def latency(self, service: str, ms: float) -> dict[str, Any]:
        """Add ``ms`` milliseconds to every request handled by the service."""
        if not 0 <= ms <= 60_000:
            return {
                "action": "latency",
                "service": service,
                "ok": False,
                "error": "ms must be between 0 and 60000",
            }
        return self._post_chaos("latency", service, "/_chaos/latency", {"ms": ms})

    def memory(self, service: str, mb: int) -> dict[str, Any]:
        """Allocate and hold ``mb`` megabytes inside the service process."""
        if not 0 <= mb <= 1024:
            return {
                "action": "memory",
                "service": service,
                "ok": False,
                "error": "mb must be between 0 and 1024",
            }
        return self._post_chaos("memory", service, "/_chaos/memory", {"mb": mb})

    def reset_all(self) -> dict[str, Any]:
        """Clear latency and release memory on every service."""
        started = time.perf_counter()
        results: dict[str, dict[str, Any]] = {}
        for service in ALL_SERVICES:
            results[service] = self._post_chaos(
                "reset", service, "/_chaos/reset", {}
            )
        return {
            "action": "reset_all",
            "ok": all(result.get("ok", False) for result in results.values()),
            "services": results,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    @staticmethod
    def _invalid(service: str, action: str, started: float) -> dict[str, Any]:
        return {
            "action": action,
            "service": service,
            "ok": False,
            "error": f"unknown service: {service}",
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }
