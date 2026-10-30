"""Pydantic schemas for agent plans and postmortems."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FaultKind = Literal["kill", "latency", "memory"]

_ONE_SENTENCE = re.compile(r"^(.+?[.!?])(?:\s|$)")


class ExperimentPlan(BaseModel):
    """A validated experiment proposal produced by the planner."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    fault: FaultKind
    target: str = Field(min_length=1, max_length=64)
    hypothesis: str = Field(min_length=1, max_length=280)
    value: float | None = None
    source: Literal["llm", "rule"] = "llm"

    @field_validator("hypothesis")
    @classmethod
    def _single_sentence(cls, value: str) -> str:
        """Keep the hypothesis to one sentence, even if the model rambles."""
        text = " ".join(value.split())
        match = _ONE_SENTENCE.match(text)
        if match:
            text = match.group(1)
        if not text.endswith((".", "!", "?")):
            text += "."
        return text

    @model_validator(mode="after")
    def _fill_value(self) -> ExperimentPlan:
        if self.fault == "kill":
            self.value = None
        elif self.value is None:
            self.value = 2_000.0 if self.fault == "latency" else 256.0
        return self


class PostmortemDraft(BaseModel):
    """The JSON shape requested from the postmortem LLM."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    root_cause: str = Field(min_length=1, max_length=600)
    blast_radius: str = Field(min_length=1, max_length=600)
    fixes: list[str] = Field(min_length=1, max_length=8)

    @field_validator("fixes")
    @classmethod
    def _clean_fixes(cls, value: list[str]) -> list[str]:
        cleaned = [" ".join(item.split()) for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("at least one fix is required")
        return cleaned


class Postmortem(BaseModel):
    """A short, structured report with a rendered text form."""

    model_config = ConfigDict(extra="ignore")

    root_cause: str
    blast_radius: str
    fixes: list[str]
    text: str
    word_count: int
    source: Literal["llm", "template"]
