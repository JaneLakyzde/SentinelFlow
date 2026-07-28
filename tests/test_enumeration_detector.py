"""Tests for high-recall parameter-enumeration candidate detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentinelflow.core.models import EventWindow, EvidenceType
from sentinelflow.core.normalization import normalize_event
from sentinelflow.detectors.config import load_parameter_enumeration_config
from sentinelflow.detectors.enumeration import (
    FIXED_STEP_RULE,
    RANDOM_RULE,
    SEQUENCE_RULE,
    detect_parameter_enumeration,
)
from sentinelflow.features.parameters import parameter_window_features

ROOT = Path(__file__).parents[1]
CONFIG = load_parameter_enumeration_config(ROOT / "configs/parameter-enumeration.yaml")


def window(values: list[int], *, parameter: str = "posid", statuses: list[int] | None = None):
    start = datetime(2026, 7, 1, 12, tzinfo=UTC)
    statuses = statuses or [200] * len(values)
    events = tuple(
        normalize_event(
            {
                "timestamp": (start + timedelta(seconds=index)).isoformat(),
                "request_id": f"req-{index}",
                "actor": "client-a",
                "source_ip": "10.0.0.1",
                "method": "GET",
                "path": "/items",
                "body": {parameter: value, "tenant": "tenant-a"},
                "http_status": statuses[index],
            },
            source="fixture.jsonl",
            line_number=index + 1,
        )
        for index, value in enumerate(values)
    )
    return EventWindow(
        window_id="window-test",
        entity_key=("client-a", "10.0.0.1", "/items"),
        start_time=start,
        end_time=start + timedelta(seconds=60),
        events=events,
    )


def detect(values: list[int], *, parameter: str = "posid", statuses: list[int] | None = None):
    event_window = window(values, parameter=parameter, statuses=statuses)
    features = parameter_window_features(event_window, parameter_path=f"body.{parameter}")
    return detect_parameter_enumeration(event_window, features, config=CONFIG)


def test_detects_consecutive_enumeration() -> None:
    candidate = detect([100, 101, 102, 103, 104])

    assert candidate is not None
    assert SEQUENCE_RULE in candidate.triggered_rule_ids
    assert candidate.sequence_numbers == (1, 2, 3, 4, 5)
    assert EvidenceType.CONSECUTIVE_SEQUENCE in {item.evidence_type for item in candidate.evidence}


def test_detects_fixed_step_enumeration() -> None:
    candidate = detect([100, 110, 120, 130, 140])

    assert candidate is not None
    assert FIXED_STEP_RULE in candidate.triggered_rule_ids
    assert candidate.to_dict()["features"]["numeric_span"] == 40


def test_detects_random_high_cardinality() -> None:
    candidate = detect([901, 17, 642, 88, 1200, 333, 5, 777])

    assert candidate is not None
    assert RANDOM_RULE in candidate.triggered_rule_ids
    assert EvidenceType.RANDOM_HIGH_CARDINALITY in {
        item.evidence_type for item in candidate.evidence
    }


def test_failure_distribution_can_raise_high_recall_candidate() -> None:
    candidate = detect(
        [10, 30, 80, 160, 320],
        statuses=[404, 404, 404, 200, 200],
    )

    assert candidate is not None
    assert candidate.to_dict()["features"]["failure_ratio"] == 0.6


def test_does_not_emit_below_minimum_cardinality() -> None:
    assert detect([100, 101, 102, 103]) is None


def test_suppresses_declared_pagination_parameter() -> None:
    assert detect([1, 2, 3, 4, 5, 6, 7, 8], parameter="page") is None


def test_mixed_non_adjacent_numeric_values_do_not_crash() -> None:
    event_window = window([1, 2, 3, 4, 5])
    mixed_events = tuple(
        normalize_event(
            {
                **dict(event.raw_record),
                "body": {
                    "posid": value,
                    "tenant": "tenant-a",
                },
            },
            source="fixture.jsonl",
            line_number=index + 1,
        )
        for index, (event, value) in enumerate(
            zip(event_window.events, [1, "x", 2, "y", 3], strict=True)
        )
    )
    mixed_window = EventWindow(
        window_id="window-mixed",
        entity_key=event_window.entity_key,
        start_time=event_window.start_time,
        end_time=event_window.end_time,
        events=mixed_events,
    )
    features = parameter_window_features(mixed_window, parameter_path="body.posid")

    assert detect_parameter_enumeration(mixed_window, features, config=CONFIG) is None


def test_rejects_features_longer_than_configured_window() -> None:
    event_window = window([100, 101, 102, 103, 104])
    features = parameter_window_features(event_window, parameter_path="body.posid")
    invalid_features = features.__class__(
        **{
            field: getattr(features, field)
            for field in features.__dataclass_fields__
            if field != "duration_seconds"
        },
        duration_seconds=CONFIG.duration_seconds + 1,
    )

    with pytest.raises(ValueError, match="duration"):
        detect_parameter_enumeration(event_window, invalid_features, config=CONFIG)
