"""Shared HTTP dependency client with optional resilience.

Default mode is deliberately fragile: one attempt, a 5 second timeout, no
circuit breaker. Setting RESILIENT=true in the service environment enables one
retry, a 1 second timeout and a per-dependency circuit breaker that returns a
caller-supplied fallback response.

Every LLM-free, credential-free sample service uses this module, so the
before/after behaviour is identical across the stack.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import httpx

LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5.0
RESILIENT_TIMEOUT_SECONDS = 1.0
RETRY_DELAY_SECONDS = 0.05
BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN_SECONDS = 10.0

FallbackFactory = Mapping[str, Any] | Callable[[str], Mapping[str, Any]]


class DependencyError(RuntimeError):
    """Raised in default mode when a dependency cannot answer."""

    def __init__(self, dependency: str, detail: str) -> None:
        super().__init__(detail)
        self.dependency = dependency
        self.detail = detail


@dataclass
class CircuitBreaker:
    """Minimal consecutive-failure breaker (closed → open → closed)."""

    failures: int = 0
    opened_at: float | None = None

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= BREAKER_COOLDOWN_SECONDS:
            self.failures = 0
            self.opened_at = None
            return False
        return True

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= BREAKER_THRESHOLD:
            self.opened_at = time.monotonic()

    @property
    def state(self) -> str:
        return "open" if self.is_open() else "closed"


class DependencyClient:
    """Calls dependencies over HTTP using the configured resilience profile."""

    def __init__(self, service_name: str, resilient: bool) -> None:
        self.service_name = service_name
        self.resilient = resilient
        self.timeout_seconds = (
            RESILIENT_TIMEOUT_SECONDS if resilient else DEFAULT_TIMEOUT_SECONDS
        )
        self.retries = 1 if resilient else 0
        self.breakers: dict[str, CircuitBreaker] = {}

    def breaker_state(self, dependency: str) -> str:
        breaker = self.breakers.get(dependency)
        return breaker.state if breaker else "closed"

    async def get(
        self,
        url: str,
        *,
        fallback: FallbackFactory | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request("GET", url, fallback=fallback, params=params)

    async def post(
        self,
        url: str,
        *,
        payload: Mapping[str, Any] | None = None,
        fallback: FallbackFactory | None = None,
    ) -> dict[str, Any]:
        return await self._request("POST", url, fallback=fallback, payload=payload)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        fallback: FallbackFactory | None,
        params: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.resilient:
            return await self._request_once(method, url, params=params, payload=payload)

        breaker = self.breakers.setdefault(url, CircuitBreaker())
        if breaker.is_open():
            LOGGER.warning("Circuit open for %s; returning fallback", url)
            return self._fallback(fallback, url, "circuit breaker open")

        last_error = "unknown dependency failure"
        for attempt in range(self.retries + 1):
            try:
                result = await self._request_once(
                    method, url, params=params, payload=payload
                )
                breaker.record_success()
                return result
            except DependencyError as exc:
                last_error = exc.detail
                LOGGER.warning(
                    "Dependency call failed (%s attempt %s/%s): %s",
                    url,
                    attempt + 1,
                    self.retries + 1,
                    exc.detail,
                )
                if attempt < self.retries:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)

        breaker.record_failure()
        return self._fallback(fallback, url, last_error)

    async def _request_once(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None,
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(
                    method, url, params=params, json=payload
                )
                response.raise_for_status()
                data: Any = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DependencyError(url, f"{type(exc).__name__}: {exc}") from exc

        if not isinstance(data, dict):
            raise DependencyError(url, "dependency returned a non-object JSON body")
        return data

    def _fallback(
        self,
        fallback: FallbackFactory | None,
        url: str,
        reason: str,
    ) -> dict[str, Any]:
        if fallback is None:
            raise DependencyError(url, reason)
        payload = dict(fallback(url)) if callable(fallback) else dict(fallback)
        payload.setdefault("degraded", True)
        payload["fallback"] = True
        payload["fallback_reason"] = reason
        payload["dependency"] = url
        return payload
