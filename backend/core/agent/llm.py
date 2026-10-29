"""LLM clients. All provider traffic stays inside the backend process."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from core.config import LLMSettings

LOGGER = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """Raised when a provider cannot answer (offline, bad response, no key)."""


class LLMClient(Protocol):
    name: str
    model: str

    async def complete(self, system_prompt: str, user_prompt: str) -> str: ...


@dataclass
class OllamaClient:
    base_url: str
    model: str
    timeout: float
    temperature: float
    max_tokens: int
    name: str = "ollama"

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url.rstrip('/')}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMUnavailable(f"ollama request failed: {exc}") from exc

        content = (data.get("message") or {}).get("content") or data.get("response")
        if not isinstance(content, str) or not content.strip():
            raise LLMUnavailable("ollama returned an empty response")
        return content


@dataclass
class OpenAICompatibleClient:
    base_url: str
    model: str
    api_key: str
    timeout: float
    temperature: float
    max_tokens: int
    name: str = "openai"

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Never include headers/request bodies in logs: they contain the key.
            raise LLMUnavailable(f"openai request failed: {type(exc).__name__}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailable("unexpected openai response shape") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMUnavailable("openai returned an empty response")
        return content


def build_client(settings: LLMSettings) -> LLMClient | None:
    """Return a client, or None when the selected provider is not usable."""
    if settings.provider == "ollama":
        return OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.timeout_seconds,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )

    api_key = settings.api_key
    if not api_key:
        LOGGER.info("Hosted LLM selected but no API key is configured")
        return None
    return OpenAICompatibleClient(
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        api_key=api_key,
        timeout=settings.timeout_seconds,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    )
