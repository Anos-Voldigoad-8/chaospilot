"""LLM plumbing shared by the planner and the postmortem writer.

All provider traffic stays in the backend. The selected provider is read from
the existing ``core.config.LLMSettings`` (``LLM_PROVIDER`` in ``.env``), so no
secret ever reaches the browser or the logs.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from core.agent.llm import LLMClient, build_client
from core.config import get_llm_settings

LOGGER = logging.getLogger(__name__)

_FENCE = re.compile(r"^```(?:json)?|```$", flags=re.MULTILINE)


def default_client() -> LLMClient | None:
    """Build the configured client, or return None when it is unusable."""
    try:
        return build_client(get_llm_settings())
    except Exception as exc:  # a broken provider config must not stop the API
        LOGGER.warning("agent LLM configuration failed: %s", type(exc).__name__)
        return None


def extract_json_object(raw: str) -> dict[str, Any]:
    """Extract one JSON object from an LLM response, tolerating fences."""
    cleaned = _FENCE.sub("", raw.strip()).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("response did not contain a JSON object")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("response JSON is not an object")
    return payload
