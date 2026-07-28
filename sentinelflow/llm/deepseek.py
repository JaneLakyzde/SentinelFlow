"""DeepSeek OpenAI-compatible Chat Completions adapter."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sentinelflow.llm.client import LLMRequest, LLMResponse, LLMUsage
from sentinelflow.llm.settings import LLMSettings


class LLMServiceError(RuntimeError):
    """Raised for safe-to-display provider or transport failures."""


class DeepSeekClient:
    """Call DeepSeek through its OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        opener: Callable[..., Any] = urlopen,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._opener = opener
        self._sleep = sleep

    @property
    def cache_identity(self) -> dict[str, object]:
        return self._settings.public_identity()

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict[str, object] = {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "stream": False,
            "max_tokens": self._settings.max_tokens,
            "response_format": {"type": self._settings.response_format},
            "thinking": {"type": self._settings.thinking},
        }
        if self._settings.thinking == "disabled":
            payload["temperature"] = self._settings.temperature
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        http_request = Request(
            f"{self._settings.base_url}/chat/completions",
            data=encoded,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._settings.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "SentinelFlow/0.1",
            },
        )

        started = time.perf_counter()
        response_payload = self._send_with_retries(http_request)
        latency_ms = (time.perf_counter() - started) * 1000
        return _parse_response(
            response_payload,
            provider=self._settings.provider,
            requested_model=self._settings.model,
            latency_ms=latency_ms,
        )

    def _send_with_retries(self, request: Request) -> dict[str, object]:
        last_error: Exception | None = None
        for attempt in range(self._settings.max_retries + 1):
            try:
                with self._opener(request, timeout=self._settings.timeout_seconds) as response:
                    raw_body = response.read()
                payload = json.loads(raw_body)
                if not isinstance(payload, dict):
                    raise LLMServiceError("DeepSeek returned a non-object JSON response")
                return payload
            except HTTPError as error:
                last_error = error
                if error.code not in {408, 429, 500, 502, 503, 504}:
                    raise LLMServiceError(
                        f"DeepSeek request failed with HTTP {error.code}"
                    ) from error
            except (TimeoutError, URLError) as error:
                last_error = error
            except json.JSONDecodeError as error:
                raise LLMServiceError("DeepSeek returned invalid JSON") from error

            if attempt < self._settings.max_retries:
                self._sleep(min(2**attempt, 4))

        assert last_error is not None
        raise LLMServiceError(
            f"DeepSeek request failed after {self._settings.max_retries + 1} attempts"
        ) from last_error


def _parse_response(
    payload: dict[str, object],
    *,
    provider: str,
    requested_model: str,
    latency_ms: float,
) -> LLMResponse:
    try:
        choices = payload["choices"]
        if not isinstance(choices, list) or not choices:
            raise TypeError
        choice = choices[0]
        if not isinstance(choice, dict):
            raise TypeError
        message = choice["message"]
        if not isinstance(message, dict):
            raise TypeError
        content = message["content"]
        if not isinstance(content, str) or not content.strip():
            raise TypeError
    except (KeyError, TypeError) as error:
        raise LLMServiceError("DeepSeek response did not contain model content") from error

    response_model = payload.get("model", requested_model)
    if not isinstance(response_model, str):
        response_model = requested_model
    usage_payload = payload.get("usage", {})
    if not isinstance(usage_payload, dict):
        usage_payload = {}
    usage = LLMUsage(
        prompt_tokens=_optional_int(usage_payload.get("prompt_tokens")),
        completion_tokens=_optional_int(usage_payload.get("completion_tokens")),
        total_tokens=_optional_int(usage_payload.get("total_tokens")),
    )
    return LLMResponse(
        content=content,
        provider=provider,
        requested_model=requested_model,
        response_model=response_model,
        latency_ms=latency_ms,
        usage=usage,
    )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
