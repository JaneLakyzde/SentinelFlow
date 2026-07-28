"""Provider-independent LLM client contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """One constrained structured-generation request."""

    system_prompt: str
    user_prompt: str
    response_schema: dict[str, object]


class LLMClient(Protocol):
    """Minimal interface implemented by concrete model providers."""

    def generate(self, request: LLMRequest) -> str:
        """Return one JSON object as text."""
        ...
