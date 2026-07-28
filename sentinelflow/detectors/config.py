"""Strict configuration loading for parameter-enumeration detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class ParameterEnumerationConfig:
    """Versioned deterministic thresholds used by the candidate detector."""

    version: str
    baseline_version: str | None
    duration_seconds: int
    overlap_seconds: int
    minimum_distinct_values: int
    minimum_numeric_values: int
    minimum_sequence_ratio: float
    minimum_fixed_step_ratio: float
    minimum_random_distinct_values: int
    maximum_random_sequence_ratio: float
    minimum_failure_ratio: float
    minimum_stable_context_ratio: float
    failure_statuses: tuple[int, ...]
    pagination_parameter_names: tuple[str, ...]
    suppress_pagination_parameters: bool

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("config version must be non-empty")
        if self.duration_seconds <= 0:
            raise ValueError("window.duration_seconds must be positive")
        if self.overlap_seconds < 0 or self.overlap_seconds >= self.duration_seconds:
            raise ValueError(
                "window.overlap_seconds must be non-negative and shorter than duration"
            )
        for name in (
            "minimum_distinct_values",
            "minimum_numeric_values",
            "minimum_random_distinct_values",
        ):
            if getattr(self, name) < 2:
                raise ValueError(f"thresholds.{name} must be at least 2")
        for name in (
            "minimum_sequence_ratio",
            "minimum_fixed_step_ratio",
            "maximum_random_sequence_ratio",
            "minimum_failure_ratio",
            "minimum_stable_context_ratio",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"thresholds.{name} must be between 0 and 1")
        if not self.failure_statuses or any(
            status < 100 or status > 599 for status in self.failure_statuses
        ):
            raise ValueError("responses.failure_statuses must contain valid HTTP statuses")
        if not self.pagination_parameter_names or any(
            not name for name in self.pagination_parameter_names
        ):
            raise ValueError("benign_patterns.pagination_parameter_names must be non-empty")


def load_parameter_enumeration_config(path: Path | str) -> ParameterEnumerationConfig:
    """Load a YAML file, rejecting missing, mistyped, and unknown keys."""
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"invalid YAML in {config_path}: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError("parameter-enumeration config must be a mapping")

    _require_exact_keys(
        raw,
        {
            "version",
            "baseline_version",
            "window",
            "thresholds",
            "responses",
            "benign_patterns",
        },
        "root",
    )
    window = _mapping(raw["window"], "window")
    thresholds = _mapping(raw["thresholds"], "thresholds")
    responses = _mapping(raw["responses"], "responses")
    benign = _mapping(raw["benign_patterns"], "benign_patterns")
    _require_exact_keys(window, {"duration_seconds", "overlap_seconds"}, "window")
    _require_exact_keys(
        thresholds,
        {
            "minimum_distinct_values",
            "minimum_numeric_values",
            "minimum_sequence_ratio",
            "minimum_fixed_step_ratio",
            "minimum_random_distinct_values",
            "maximum_random_sequence_ratio",
            "minimum_failure_ratio",
            "minimum_stable_context_ratio",
        },
        "thresholds",
    )
    _require_exact_keys(responses, {"failure_statuses"}, "responses")
    _require_exact_keys(
        benign,
        {"pagination_parameter_names", "suppress_pagination_parameters"},
        "benign_patterns",
    )

    failure_statuses = _integer_list(responses["failure_statuses"], "responses.failure_statuses")
    pagination_names = _string_list(
        benign["pagination_parameter_names"],
        "benign_patterns.pagination_parameter_names",
    )
    baseline = raw["baseline_version"]
    if baseline is not None and not isinstance(baseline, str):
        raise ValueError("baseline_version must be a string or null")

    return ParameterEnumerationConfig(
        version=_string(raw["version"], "version"),
        baseline_version=baseline,
        duration_seconds=_integer(window["duration_seconds"], "window.duration_seconds"),
        overlap_seconds=_integer(window["overlap_seconds"], "window.overlap_seconds"),
        minimum_distinct_values=_integer(
            thresholds["minimum_distinct_values"], "thresholds.minimum_distinct_values"
        ),
        minimum_numeric_values=_integer(
            thresholds["minimum_numeric_values"], "thresholds.minimum_numeric_values"
        ),
        minimum_sequence_ratio=_number(
            thresholds["minimum_sequence_ratio"], "thresholds.minimum_sequence_ratio"
        ),
        minimum_fixed_step_ratio=_number(
            thresholds["minimum_fixed_step_ratio"], "thresholds.minimum_fixed_step_ratio"
        ),
        minimum_random_distinct_values=_integer(
            thresholds["minimum_random_distinct_values"],
            "thresholds.minimum_random_distinct_values",
        ),
        maximum_random_sequence_ratio=_number(
            thresholds["maximum_random_sequence_ratio"],
            "thresholds.maximum_random_sequence_ratio",
        ),
        minimum_failure_ratio=_number(
            thresholds["minimum_failure_ratio"], "thresholds.minimum_failure_ratio"
        ),
        minimum_stable_context_ratio=_number(
            thresholds["minimum_stable_context_ratio"],
            "thresholds.minimum_stable_context_ratio",
        ),
        failure_statuses=tuple(sorted(set(failure_statuses))),
        pagination_parameter_names=tuple(name.lower() for name in pagination_names),
        suppress_pagination_parameters=_boolean(
            benign["suppress_pagination_parameters"],
            "benign_patterns.suppress_pagination_parameters",
        ),
    )


def _require_exact_keys(value: dict[str, Any], expected: set[str], location: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing {missing}")
        if unknown:
            details.append(f"unknown {unknown}")
        raise ValueError(f"{location} keys are invalid: {', '.join(details)}")


def _mapping(value: object, location: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{location} must be a string-keyed mapping")
    return value


def _integer(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{location} must be an integer")
    return value


def _number(value: object, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{location} must be a number")
    return float(value)


def _string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location} must be a non-empty string")
    return value


def _boolean(value: object, location: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{location} must be a boolean")
    return value


def _integer_list(value: object, location: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{location} must be a non-empty list")
    return [_integer(item, location) for item in value]


def _string_list(value: object, location: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{location} must be a non-empty list")
    return [_string(item, location) for item in value]
