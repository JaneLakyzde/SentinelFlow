"""Deterministic parameter-distribution features for API event windows."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import pairwise
from typing import Any, TypeAlias

from sentinelflow.core.models import AuditEvent, EventWindow

JsonScalar: TypeAlias = str | int | float | bool | None
_MISSING = object()


@dataclass(frozen=True, slots=True)
class ParameterWindowFeatures:
    """Measured evidence used by parameter-enumeration candidate detectors."""

    window_id: str
    entity_key: tuple[str, ...]
    parameter_path: str
    event_count: int
    observed_value_count: int
    missing_value_count: int
    distinct_value_count: int
    numeric_value_count: int
    numeric_minimum: float | None
    numeric_maximum: float | None
    numeric_span: float | None
    ascending_ratio: float | None
    descending_ratio: float | None
    consecutive_ratio: float | None
    fixed_step_ratio: float | None
    entropy_bits: float
    duration_seconds: float
    stable_context_ratio: float
    status_counts: tuple[tuple[int | None, int], ...]
    sequence_numbers: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        result = asdict(self)
        result["entity_key"] = list(self.entity_key)
        result["status_counts"] = {
            "null" if status is None else str(status): count for status, count in self.status_counts
        }
        result["sequence_numbers"] = list(self.sequence_numbers)
        return result


def extract_parameter(event: AuditEvent, parameter_path: str) -> JsonScalar | object:
    """Extract a scalar from ``body`` using ``body.a.b`` or ``a.b`` notation."""
    parts = _path_parts(parameter_path)
    current: object = event.body
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    if isinstance(current, Mapping | Sequence) and not isinstance(current, str):
        return _MISSING
    if not isinstance(current, str | int | float | bool) and current is not None:
        return _MISSING
    return current


def parameter_window_features(
    window: EventWindow,
    *,
    parameter_path: str,
) -> ParameterWindowFeatures:
    """Compute reproducible distribution and sequence features for one window."""
    parts = _path_parts(parameter_path)
    values: list[JsonScalar] = []
    numeric_sequence: list[float | None] = []
    observed_events: list[AuditEvent] = []
    contexts: Counter[str] = Counter()

    for event in window.events:
        value = extract_parameter(event, parameter_path)
        if value is _MISSING:
            continue
        assert isinstance(value, str | int | float | bool) or value is None
        values.append(value)
        numeric_sequence.append(_numeric_value(value))
        observed_events.append(event)
        contexts[_context_fingerprint(event, parts)] += 1

    numeric_values = [value for value in numeric_sequence if value is not None]
    distinct_count = len({_canonical_scalar(value) for value in values})
    numeric_minimum = min(numeric_values) if numeric_values else None
    numeric_maximum = max(numeric_values) if numeric_values else None
    numeric_span = (
        numeric_maximum - numeric_minimum
        if numeric_minimum is not None and numeric_maximum is not None
        else None
    )
    ascending, descending, consecutive, fixed_step = _sequence_ratios(numeric_sequence)
    status_counts = tuple(
        sorted(
            Counter(event.http_status for event in observed_events).items(),
            key=lambda item: -1 if item[0] is None else item[0],
        )
    )
    duration = (
        (observed_events[-1].timestamp - observed_events[0].timestamp).total_seconds()
        if len(observed_events) > 1
        else 0.0
    )
    stable_context_ratio = max(contexts.values()) / len(values) if values else 0.0

    return ParameterWindowFeatures(
        window_id=window.window_id,
        entity_key=window.entity_key,
        parameter_path="body." + ".".join(parts),
        event_count=len(window.events),
        observed_value_count=len(values),
        missing_value_count=len(window.events) - len(values),
        distinct_value_count=distinct_count,
        numeric_value_count=len(numeric_values),
        numeric_minimum=numeric_minimum,
        numeric_maximum=numeric_maximum,
        numeric_span=numeric_span,
        ascending_ratio=ascending,
        descending_ratio=descending,
        consecutive_ratio=consecutive,
        fixed_step_ratio=fixed_step,
        entropy_bits=_entropy(values),
        duration_seconds=duration,
        stable_context_ratio=stable_context_ratio,
        status_counts=status_counts,
        sequence_numbers=tuple(event.sequence_no for event in observed_events),
    )


def _path_parts(parameter_path: str) -> tuple[str, ...]:
    normalized = parameter_path.strip()
    if normalized.startswith("body."):
        normalized = normalized[5:]
    parts = tuple(part for part in normalized.split(".") if part)
    if not parts:
        raise ValueError("parameter path must identify a field inside body")
    return parts


def _numeric_value(value: JsonScalar) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        numeric = float(value)
    elif isinstance(value, str):
        try:
            numeric = float(value)
        except ValueError:
            return None
    else:
        return None
    return numeric if math.isfinite(numeric) else None


def _sequence_ratios(
    values: list[float | None],
) -> tuple[float | None, float | None, float | None, float | None]:
    differences = [
        right - left for left, right in pairwise(values) if left is not None and right is not None
    ]
    if not differences:
        return None, None, None, None
    pair_count = len(differences)
    ascending = sum(diff > 0 for diff in differences) / pair_count
    descending = sum(diff < 0 for diff in differences) / pair_count
    consecutive = sum(abs(diff) == 1 for diff in differences) / pair_count
    nonzero = [diff for diff in differences if diff != 0]
    fixed_step = max(Counter(nonzero).values()) / pair_count if nonzero else 0.0
    return ascending, descending, consecutive, fixed_step


def _entropy(values: list[JsonScalar]) -> float:
    if not values:
        return 0.0
    counts = Counter(_canonical_scalar(value) for value in values)
    total = len(values)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def _canonical_scalar(value: JsonScalar) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _context_fingerprint(event: AuditEvent, parameter_parts: tuple[str, ...]) -> str:
    body_without_target = _without_path(event.body, parameter_parts)
    return json.dumps(
        {
            "method": event.method,
            "path": event.path,
            "body": body_without_target,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _without_path(value: object, parts: tuple[str, ...]) -> object:
    if not parts or not isinstance(value, Mapping):
        return _json_value(value)
    target = next(iter(parts))
    remaining = parts[1:]
    result: dict[str, object] = {}
    for key, item in value.items():
        key_text = str(key)
        if key_text != target:
            result[key_text] = _json_value(item)
        elif remaining:
            result[key_text] = _without_path(item, remaining)
    return result


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    return value
