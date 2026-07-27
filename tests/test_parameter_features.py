"""Tests for deterministic parameter-distribution features."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from sentinelflow.core.models import EventWindow
from sentinelflow.core.normalization import normalize_event
from sentinelflow.features.parameters import parameter_window_features


def event(
    second: int,
    value: object,
    *,
    status: int | None = 200,
    body_override: object | None = None,
):
    body = (
        body_override
        if body_override is not None
        else {"resource": {"id": value}, "tenant": "tenant-a"}
    )
    return normalize_event(
        {
            "timestamp": f"2026-07-01T12:00:0{second}Z",
            "request_id": f"req-{second}",
            "actor": "client-a",
            "source_ip": "10.0.0.1",
            "method": "GET",
            "path": "/api/items",
            "body": body,
            "http_status": status,
        },
        source="fixture.jsonl",
        line_number=second + 1,
    )


def test_parameter_features_measure_order_distribution_and_context() -> None:
    events = (
        event(0, 10, status=200),
        event(1, 11, status=404),
        event(2, "12", status=404),
        event(3, 13, status=200),
    )
    window = EventWindow(
        window_id="window-test",
        entity_key=("client-a", "10.0.0.1", "/api/items"),
        start_time=datetime(2026, 7, 1, 12, tzinfo=UTC),
        end_time=datetime(2026, 7, 1, 12, 1, tzinfo=UTC),
        events=events,
    )

    features = parameter_window_features(window, parameter_path="body.resource.id")

    assert features.event_count == 4
    assert features.observed_value_count == 4
    assert features.missing_value_count == 0
    assert features.distinct_value_count == 4
    assert features.numeric_value_count == 4
    assert features.numeric_minimum == 10
    assert features.numeric_maximum == 13
    assert features.numeric_span == 3
    assert features.ascending_ratio == 1
    assert features.descending_ratio == 0
    assert features.consecutive_ratio == 1
    assert features.fixed_step_ratio == 1
    assert features.entropy_bits == 2
    assert features.duration_seconds == 3
    assert features.stable_context_ratio == 1
    assert features.status_counts == ((200, 2), (404, 2))
    assert features.sequence_numbers == (1, 2, 3, 4)


def test_missing_and_non_scalar_values_are_not_observed() -> None:
    events = (
        event(0, 1, status=500, body_override={"resource": {}}),
        event(1, 1, status=404, body_override={"resource": {"id": [1, 2]}}),
        event(2, None),
    )
    window = EventWindow(
        window_id="window-missing",
        entity_key=("client-a", "10.0.0.1", "/api/items"),
        start_time=events[0].timestamp,
        end_time=events[0].timestamp + timedelta(seconds=60),
        events=events,
    )

    features = parameter_window_features(window, parameter_path="resource.id")

    assert features.observed_value_count == 1
    assert features.missing_value_count == 2
    assert features.distinct_value_count == 1
    assert features.numeric_value_count == 0
    assert features.ascending_ratio is None
    assert features.stable_context_ratio == 1
    assert features.status_counts == ((200, 1),)
    assert features.sequence_numbers == (3,)


def test_entropy_counts_repeated_values() -> None:
    events = (event(0, "a"), event(1, "a"), event(2, "b"), event(3, "b"))
    window = EventWindow(
        window_id="window-entropy",
        entity_key=("client-a",),
        start_time=events[0].timestamp,
        end_time=events[0].timestamp + timedelta(seconds=60),
        events=events,
    )

    features = parameter_window_features(window, parameter_path="resource.id")
    assert math.isclose(features.entropy_bits, 1.0)
    assert features.numeric_value_count == 0
    assert features.fixed_step_ratio is None


def test_non_numeric_values_break_numeric_adjacency() -> None:
    events = (event(0, 1), event(1, "not-a-number"), event(2, 2))
    window = EventWindow(
        window_id="window-mixed",
        entity_key=("client-a",),
        start_time=events[0].timestamp,
        end_time=events[0].timestamp + timedelta(seconds=60),
        events=events,
    )

    features = parameter_window_features(window, parameter_path="resource.id")
    assert features.numeric_value_count == 2
    assert features.ascending_ratio is None
    assert features.consecutive_ratio is None
    assert features.fixed_step_ratio is None
