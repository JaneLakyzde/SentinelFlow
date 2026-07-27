"""Normalization for raw API audit records."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

from sentinelflow.core.errors import EventValidationError
from sentinelflow.core.models import AuditEvent

_MULTIPLE_SLASHES = re.compile(r"/+")
_MISSING = object()


def parse_timestamp(value: object) -> datetime:
    """Parse an ISO 8601 timestamp and return an aware UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("field 'timestamp' must be a non-empty ISO 8601 string")

    text = value.strip()
    if text.endswith(("Z", "z")):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"field 'timestamp' is not valid ISO 8601: {value!r}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("field 'timestamp' must include a timezone")
    return parsed.astimezone(UTC)


def normalize_path(value: object) -> str:
    """Normalize an HTTP path and remove its query string and fragment."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("field 'path' must be a non-empty string")

    text = value.strip()
    try:
        split = urlsplit(text)
    except ValueError as error:
        raise ValueError(f"field 'path' is not a valid path: {value!r}") from error

    path = split.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    path = _MULTIPLE_SLASHES.sub("/", path)
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def normalize_event(
    raw: Mapping[str, Any],
    *,
    source: Path | str,
    line_number: int,
) -> AuditEvent:
    """Validate and normalize one decoded JSON object."""
    try:
        timestamp = parse_timestamp(_required(raw, "timestamp"))
        request_id = _required_text(raw, "request_id")
        actor = _required_text(raw, "actor")
        source_ip = _required_text(raw, "source_ip")
        method = _required_text(raw, "method").upper()
        path = normalize_path(_required(raw, "path"))
        sequence_no = _sequence_number(raw.get("sequence_no", line_number))
        body = _body(raw.get("body", {}))
        http_status = _optional_status(raw.get("http_status"))
        response_code = _optional_text(raw.get("response_code"), "response_code")
        issued_sid = _optional_text(raw.get("issued_sid"), "issued_sid")
    except ValueError as error:
        raise EventValidationError(str(error), source=source, line_number=line_number) from error

    frozen_raw = _freeze_json(raw)
    assert isinstance(frozen_raw, Mapping)
    return AuditEvent(
        sequence_no=sequence_no,
        timestamp=timestamp,
        request_id=request_id,
        actor=actor,
        source_ip=source_ip,
        method=method,
        path=path,
        body=body,
        http_status=http_status,
        response_code=response_code,
        issued_sid=issued_sid,
        raw_record=frozen_raw,
        raw_line_number=line_number,
    )


def _required(raw: Mapping[str, Any], field: str) -> Any:
    value = raw.get(field, _MISSING)
    if value is _MISSING or value is None:
        raise ValueError(f"missing required field '{field}'")
    return value


def _required_text(raw: Mapping[str, Any], field: str) -> str:
    value = _required(raw, field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"field '{field}' must be a non-empty string")
    return value.strip()


def _optional_text(value: object, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"field '{field}' must be a string or null")
    normalized = value.strip()
    return normalized or None


def _sequence_number(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("field 'sequence_no' must be a positive integer")
    return value


def _body(value: object) -> Mapping[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise ValueError("field 'body' must be an object or null")
    frozen = _freeze_json(value)
    assert isinstance(frozen, Mapping)
    return frozen


def _optional_status(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("field 'http_status' must be an integer or null")
    if isinstance(value, str):
        try:
            value = int(value.strip())
        except ValueError as error:
            raise ValueError("field 'http_status' must be an integer or null") from error
    if not isinstance(value, int) or not 100 <= value <= 599:
        raise ValueError("field 'http_status' must be between 100 and 599")
    return value


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_json(item) for item in value)
    return value
