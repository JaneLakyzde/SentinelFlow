"""Streaming JSONL event reader."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Never

from sentinelflow.core.errors import InputError, JsonlDecodeError
from sentinelflow.core.models import AuditEvent
from sentinelflow.core.normalization import normalize_event


class JsonlEventReader:
    """Stream normalized events from a JSONL file without loading it all."""

    def __init__(self, path: Path | str, *, skip_invalid: bool = False) -> None:
        self.path = Path(path)
        self.skip_invalid = skip_invalid
        self.invalid_rows = 0

    def __iter__(self) -> Iterator[AuditEvent]:
        self.invalid_rows = 0
        with self.path.open("rb") as stream:
            for line_number, encoded_line in enumerate(stream, start=1):
                try:
                    line = self._decode_utf8(encoded_line, line_number)
                    raw = self._decode(line, line_number)
                    yield normalize_event(
                        raw,
                        source=self.path,
                        line_number=line_number,
                    )
                except InputError:
                    self.invalid_rows += 1
                    if not self.skip_invalid:
                        raise

    def _decode_utf8(self, line: bytes, line_number: int) -> str:
        try:
            return line.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise JsonlDecodeError(
                f"row is not valid UTF-8 (byte {error.start + 1})",
                source=self.path,
                line_number=line_number,
            ) from error

    def _decode(self, line: str, line_number: int) -> Mapping[str, Any]:
        if not line.strip():
            raise JsonlDecodeError(
                "empty JSONL row",
                source=self.path,
                line_number=line_number,
            )
        try:
            value = json.loads(line, parse_constant=_reject_non_finite_number)
        except (json.JSONDecodeError, ValueError) as error:
            detail = (
                f"{error.msg}, column {error.colno}"
                if isinstance(error, json.JSONDecodeError)
                else str(error)
            )
            raise JsonlDecodeError(
                f"invalid JSON ({detail})",
                source=self.path,
                line_number=line_number,
            ) from error
        if not isinstance(value, dict):
            raise JsonlDecodeError(
                "JSONL row must be an object",
                source=self.path,
                line_number=line_number,
            )
        return value


def _reject_non_finite_number(value: str) -> Never:
    raise ValueError(f"non-finite number {value!r} is not permitted")
