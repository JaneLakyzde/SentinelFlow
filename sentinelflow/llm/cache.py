"""Content-addressed local cache for deterministic LLM requests."""

from __future__ import annotations

import hashlib
import json
import tempfile
from contextlib import suppress
from pathlib import Path

from sentinelflow.llm.client import LLMClient, LLMRequest, LLMResponse, LLMUsage

_CACHE_VERSION = "1"


class CachedLLMClient:
    """Cache provider responses by request and model settings."""

    def __init__(self, client: LLMClient, directory: Path | str) -> None:
        self._client = client
        self._directory = Path(directory)

    @property
    def cache_identity(self) -> dict[str, object]:
        return self._client.cache_identity

    def generate(self, request: LLMRequest) -> LLMResponse:
        request_hash = self.request_hash(request)
        cache_path = self._directory / f"{request_hash}.json"
        cached = _read_cache(cache_path)
        if cached is not None:
            return LLMResponse(
                content=cached.content,
                provider=cached.provider,
                requested_model=cached.requested_model,
                response_model=cached.response_model,
                latency_ms=0.0,
                usage=cached.usage,
                cached=True,
                request_hash=request_hash,
            )

        response = self._client.generate(request)
        stored = LLMResponse(
            content=response.content,
            provider=response.provider,
            requested_model=response.requested_model,
            response_model=response.response_model,
            latency_ms=response.latency_ms,
            usage=response.usage,
            cached=False,
            request_hash=request_hash,
        )
        _write_cache(cache_path, stored)
        return stored

    def request_hash(self, request: LLMRequest) -> str:
        payload = {
            "cache_version": _CACHE_VERSION,
            "client": self.cache_identity,
            "request": {
                "system_prompt": request.system_prompt,
                "user_prompt": request.user_prompt,
                "response_schema": request.response_schema,
            },
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def invalidate(self, request: LLMRequest) -> None:
        """Remove a response that failed local schema or evidence validation."""
        cache_path = self._directory / f"{self.request_hash(request)}.json"
        with suppress(OSError):
            cache_path.unlink(missing_ok=True)


def _read_cache(path: Path) -> LLMResponse | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("cache_version") != _CACHE_VERSION:
            return None
        usage_payload = payload["usage"]
        if not isinstance(usage_payload, dict):
            return None
        content = payload["content"]
        provider = payload["provider"]
        requested_model = payload["requested_model"]
        response_model = payload["response_model"]
        latency_ms = payload["latency_ms"]
        if (
            not isinstance(content, str)
            or not isinstance(provider, str)
            or not isinstance(requested_model, str)
            or not isinstance(response_model, str)
            or isinstance(latency_ms, bool)
            or not isinstance(latency_ms, int | float)
        ):
            return None
        return LLMResponse(
            content=content,
            provider=provider,
            requested_model=requested_model,
            response_model=response_model,
            latency_ms=float(latency_ms),
            usage=LLMUsage(
                prompt_tokens=_optional_int(usage_payload.get("prompt_tokens")),
                completion_tokens=_optional_int(usage_payload.get("completion_tokens")),
                total_tokens=_optional_int(usage_payload.get("total_tokens")),
            ),
        )
    except (OSError, KeyError, json.JSONDecodeError, TypeError):
        return None


def _write_cache(path: Path, response: LLMResponse) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cache_version": _CACHE_VERSION,
        "content": response.content,
        "provider": response.provider,
        "requested_model": response.requested_model,
        "response_model": response.response_model,
        "latency_ms": response.latency_ms,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
        assert temporary_path is not None
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
