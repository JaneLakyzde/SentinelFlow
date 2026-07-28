"""DeepSeek settings, transport, and cache tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sentinelflow.llm.cache import CachedLLMClient
from sentinelflow.llm.client import LLMRequest, LLMResponse, LLMUsage
from sentinelflow.llm.deepseek import DeepSeekClient
from sentinelflow.llm.settings import LLMConfigurationError, LLMSettings


def settings(**changes: Any) -> LLMSettings:
    values = {
        "provider": "deepseek",
        "api_format": "openai-chat-completions",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-pro",
        "api_key": "secret-key",
        "thinking": "disabled",
        "temperature": 0,
        "response_format": "json_object",
        "max_tokens": 4096,
        "timeout_seconds": 60,
        "max_retries": 2,
        "cache_directory": Path("outputs/cache"),
    }
    values.update(changes)
    return LLMSettings(**values)


def request() -> LLMRequest:
    return LLMRequest(
        system_prompt="Return JSON.",
        user_prompt='Return {"ok":true}.',
        response_schema={"type": "object"},
    )


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeHTTPResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_settings_load_dotenv_and_process_environment_wins(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SENTINELFLOW_LLM_API_KEY=file-key",
                "SENTINELFLOW_LLM_MODEL=deepseek-v4-pro",
                "SENTINELFLOW_LLM_MAX_TOKENS=2048",
            ]
        ),
        encoding="utf-8",
    )

    loaded = LLMSettings.from_env(
        env_file,
        environ={"SENTINELFLOW_LLM_API_KEY": "process-key"},
    )

    assert loaded.api_key == "process-key"
    assert loaded.max_tokens == 2048
    assert "process-key" not in repr(loaded)


def test_settings_reject_placeholder_key(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SENTINELFLOW_LLM_API_KEY=replace_with_your_deepseek_api_key\n",
        encoding="utf-8",
    )

    with pytest.raises(LLMConfigurationError, match="not configured"):
        LLMSettings.from_env(env_file, environ={})


def test_deepseek_client_uses_openai_chat_json_format() -> None:
    captured: dict[str, object] = {}

    def opener(http_request, *, timeout: float):
        captured["url"] = http_request.full_url
        captured["headers"] = dict(http_request.headers)
        captured["payload"] = json.loads(http_request.data)
        captured["timeout"] = timeout
        return FakeHTTPResponse(
            {
                "model": "deepseek-v4-pro-202607",
                "choices": [{"message": {"content": '{"ok":true}'}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            }
        )

    client = DeepSeekClient(settings(), opener=opener)
    response = client.generate(request())

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["timeout"] == 60
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "deepseek-v4-pro"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["temperature"] == 0
    assert response.content == '{"ok":true}'
    assert response.response_model == "deepseek-v4-pro-202607"
    assert response.usage.total_tokens == 14


class CountingClient:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def cache_identity(self) -> dict[str, object]:
        return {"provider": "test", "model": "one"}

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            content='{"ok":true}',
            provider="test",
            requested_model="one",
            response_model="one-v1",
            latency_ms=12.5,
            usage=LLMUsage(10, 4, 14),
        )


def test_cached_client_avoids_duplicate_provider_calls(tmp_path: Path) -> None:
    provider = CountingClient()
    client = CachedLLMClient(provider, tmp_path / "cache")

    first = client.generate(request())
    second = client.generate(request())

    assert provider.calls == 1
    assert first.cached is False
    assert second.cached is True
    assert first.request_hash == second.request_hash
    assert second.usage.total_tokens == 14
