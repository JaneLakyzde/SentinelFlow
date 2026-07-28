"""Environment-backed LLM runtime settings."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


class LLMConfigurationError(ValueError):
    """Raised when LLM runtime configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """Validated DeepSeek settings loaded without exposing the API key."""

    provider: str
    api_format: str
    base_url: str
    model: str
    api_key: str = field(repr=False)
    thinking: str = "disabled"
    temperature: float = 0.0
    response_format: str = "json_object"
    max_tokens: int = 4096
    timeout_seconds: float = 60.0
    max_retries: int = 2
    cache_directory: Path = Path("outputs/cache")

    def __post_init__(self) -> None:
        if self.provider != "deepseek":
            raise LLMConfigurationError("SENTINELFLOW_LLM_PROVIDER must be deepseek")
        if self.api_format != "openai-chat-completions":
            raise LLMConfigurationError(
                "SENTINELFLOW_LLM_API_FORMAT must be openai-chat-completions"
            )
        if not self.base_url.startswith("https://"):
            raise LLMConfigurationError("SENTINELFLOW_LLM_BASE_URL must use HTTPS")
        if self.model not in {"deepseek-v4-pro", "deepseek-v4-flash"}:
            raise LLMConfigurationError(
                "SENTINELFLOW_LLM_MODEL must be deepseek-v4-pro or deepseek-v4-flash"
            )
        if not self.api_key or self.api_key == "replace_with_your_deepseek_api_key":
            raise LLMConfigurationError("SENTINELFLOW_LLM_API_KEY is not configured")
        if self.thinking not in {"enabled", "disabled"}:
            raise LLMConfigurationError("SENTINELFLOW_LLM_THINKING must be enabled or disabled")
        if self.thinking == "enabled" and self.temperature != 0:
            raise LLMConfigurationError("temperature must be 0 when thinking mode is enabled")
        if self.response_format != "json_object":
            raise LLMConfigurationError("SENTINELFLOW_LLM_RESPONSE_FORMAT must be json_object")
        if self.max_tokens < 1:
            raise LLMConfigurationError("SENTINELFLOW_LLM_MAX_TOKENS must be positive")
        if self.timeout_seconds <= 0:
            raise LLMConfigurationError("SENTINELFLOW_LLM_TIMEOUT_SECONDS must be positive")
        if self.max_retries < 0:
            raise LLMConfigurationError("SENTINELFLOW_LLM_MAX_RETRIES cannot be negative")

    @classmethod
    def from_env(
        cls,
        env_file: Path | str = Path(".env"),
        *,
        environ: Mapping[str, str] | None = None,
    ) -> LLMSettings:
        """Load a dotenv file, with process environment values taking precedence."""
        values = _read_dotenv(Path(env_file))
        values.update(dict(os.environ if environ is None else environ))

        def required(name: str) -> str:
            value = values.get(name, "").strip()
            if not value:
                raise LLMConfigurationError(f"{name} is required")
            return value

        return cls(
            provider=values.get("SENTINELFLOW_LLM_PROVIDER", "deepseek").strip(),
            api_format=values.get("SENTINELFLOW_LLM_API_FORMAT", "openai-chat-completions").strip(),
            base_url=values.get("SENTINELFLOW_LLM_BASE_URL", "https://api.deepseek.com")
            .strip()
            .rstrip("/"),
            model=values.get("SENTINELFLOW_LLM_MODEL", "deepseek-v4-pro").strip(),
            api_key=required("SENTINELFLOW_LLM_API_KEY"),
            thinking=values.get("SENTINELFLOW_LLM_THINKING", "disabled").strip(),
            temperature=_float(values, "SENTINELFLOW_LLM_TEMPERATURE", 0.0),
            response_format=values.get("SENTINELFLOW_LLM_RESPONSE_FORMAT", "json_object").strip(),
            max_tokens=_int(values, "SENTINELFLOW_LLM_MAX_TOKENS", 4096),
            timeout_seconds=_float(values, "SENTINELFLOW_LLM_TIMEOUT_SECONDS", 60.0),
            max_retries=_int(values, "SENTINELFLOW_LLM_MAX_RETRIES", 2),
            cache_directory=Path(
                values.get("SENTINELFLOW_LLM_CACHE_DIRECTORY", "outputs/cache").strip()
            ),
        )

    def public_identity(self) -> dict[str, object]:
        """Return output-affecting, non-secret settings for cache keys."""
        return {
            "provider": self.provider,
            "api_format": self.api_format,
            "base_url": self.base_url,
            "model": self.model,
            "thinking": self.thinking,
            "temperature": self.temperature,
            "response_format": self.response_format,
            "max_tokens": self.max_tokens,
        }


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if "=" not in line:
            raise LLMConfigurationError(f"{path}:{line_number}: expected NAME=VALUE")
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if not name:
            raise LLMConfigurationError(f"{path}:{line_number}: variable name is empty")
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value
    return values


def _int(values: Mapping[str, str], name: str, default: int) -> int:
    raw_value = values.get(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as error:
        raise LLMConfigurationError(f"{name} must be an integer") from error


def _float(values: Mapping[str, str], name: str, default: float) -> float:
    raw_value = values.get(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError as error:
        raise LLMConfigurationError(f"{name} must be a number") from error
