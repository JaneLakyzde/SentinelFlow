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


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Token usage reported by a provider."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """One provider response plus reproducibility metadata."""

    content: str
    provider: str
    requested_model: str
    response_model: str
    latency_ms: float
    usage: LLMUsage
    cached: bool = False
    request_hash: str | None = None

    def to_metadata_dict(self) -> dict[str, object]:
        """Return metadata without model content or credentials."""
        return {
            "provider": self.provider,
            "requested_model": self.requested_model,
            "response_model": self.response_model,
            "latency_ms": round(self.latency_ms, 3),
            "cached": self.cached,
            "request_hash": self.request_hash,
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
            },
        }


class LLMClient(Protocol):
    """Minimal interface implemented by concrete model providers."""

    @property
    def cache_identity(self) -> dict[str, object]:
        """Return non-secret settings that affect model output."""
        ...

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Return one JSON object and provider metadata."""
        ...
