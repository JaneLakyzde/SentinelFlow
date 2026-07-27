"""Errors raised while reading and normalizing audit events."""

from __future__ import annotations

from pathlib import Path


class InputError(ValueError):
    """Base class for an input error tied to a source line."""

    def __init__(self, message: str, *, source: Path | str, line_number: int) -> None:
        self.source = Path(source)
        self.line_number = line_number
        self.detail = message
        super().__init__(f"{self.source}:{self.line_number}: {message}")


class JsonlDecodeError(InputError):
    """A JSONL row is empty, malformed, or is not a JSON object."""


class EventValidationError(InputError):
    """A decoded event does not satisfy the ingestion contract."""
