"""Utilities for safe candidate projections and review output."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable, Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any

from sentinelflow.core.models import AuditEvent, Candidate


def project_candidate_events(
    events: Iterable[AuditEvent],
    candidates: Iterable[Candidate],
    *,
    maximum_string_length: int = 2048,
    maximum_object_depth: int = 8,
) -> dict[str, list[dict[str, object]]]:
    """Build minimal normalized event projections for candidate sequence numbers."""
    candidate_list = list(candidates)
    candidate_sequences = {
        candidate.candidate_id: set(candidate.sequence_numbers) for candidate in candidate_list
    }
    wanted_sequences = set().union(*candidate_sequences.values()) if candidate_sequences else set()
    projected_by_sequence: dict[int, dict[str, object]] = {}
    for event in events:
        if event.sequence_no not in wanted_sequences:
            continue
        projected_by_sequence[event.sequence_no] = {
            "sequence_no": event.sequence_no,
            "timestamp": event.timestamp.isoformat(),
            "request_id": _truncate(event.request_id, maximum_string_length),
            "actor": _truncate(event.actor, maximum_string_length),
            "source_ip": _truncate(event.source_ip, maximum_string_length),
            "method": event.method,
            "path": _truncate(event.path, maximum_string_length),
            "body": _json_safe(
                event.body,
                maximum_string_length=maximum_string_length,
                maximum_object_depth=maximum_object_depth,
            ),
            "http_status": event.http_status,
            "response_code": (
                _truncate(event.response_code, maximum_string_length)
                if event.response_code is not None
                else None
            ),
        }
    return {
        candidate.candidate_id: [
            projected_by_sequence[sequence_no]
            for sequence_no in candidate.sequence_numbers
            if sequence_no in projected_by_sequence
        ]
        for candidate in candidate_list
    }


def load_normal_context(path: Path | str | None) -> dict[str, object]:
    """Load an optional trusted normal-context JSON object."""
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("normal context must be a JSON object")
    return payload


def write_review_records(records: Iterable[Mapping[str, object]], output: Path | str) -> None:
    """Atomically write review records as UTF-8 JSONL."""
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            for record in records:
                stream.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
                stream.write("\n")
        assert temporary_path is not None
        temporary_path.replace(output_path)
    finally:
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)


def _json_safe(
    value: object,
    *,
    maximum_string_length: int,
    maximum_object_depth: int,
    _depth: int = 0,
) -> Any:
    if _depth >= maximum_object_depth:
        return "<truncated-depth>"
    if isinstance(value, Mapping):
        return {
            _truncate(str(key), maximum_string_length): _json_safe(
                item,
                maximum_string_length=maximum_string_length,
                maximum_object_depth=maximum_object_depth,
                _depth=_depth + 1,
            )
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [
            _json_safe(
                item,
                maximum_string_length=maximum_string_length,
                maximum_object_depth=maximum_object_depth,
                _depth=_depth + 1,
            )
            for item in value
        ]
    if isinstance(value, str):
        return _truncate(value, maximum_string_length)
    if value is None or isinstance(value, int | float | bool):
        return value
    return _truncate(str(value), maximum_string_length)


def _truncate(value: str, maximum_length: int) -> str:
    if len(value) <= maximum_length:
        return value
    return f"{value[:maximum_length]}…"
