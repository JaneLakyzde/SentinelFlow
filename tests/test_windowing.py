"""Tests for deterministic event windows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sentinelflow.core.models import EventWindow
from sentinelflow.core.normalization import normalize_event
from sentinelflow.core.windowing import WindowConfig, iter_event_windows


def event(second: int, *, actor: str = "client-a", sequence_no: int | None = None):
    raw: dict[str, object] = {
        "timestamp": f"2026-07-01T12:00:{second:02d}Z",
        "request_id": f"req-{second}",
        "actor": actor,
        "source_ip": "10.0.0.1",
        "method": "GET",
        "path": "/api/items",
        "body": {"posid": second},
        "http_status": 200,
    }
    if sequence_no is not None:
        raw["sequence_no"] = sequence_no
    return normalize_event(raw, source="fixture.jsonl", line_number=second + 1)


def test_non_overlapping_windows_group_events_by_entity() -> None:
    windows = list(
        iter_event_windows(
            [event(1), event(9), event(11), event(12, actor="client-b")],
            config=WindowConfig(duration=timedelta(seconds=10)),
        )
    )

    actual = [
        (window.entity_key, [item.sequence_no for item in window.events]) for window in windows
    ]
    assert actual == [
        (("client-a", "10.0.0.1", "/api/items"), [2, 10]),
        (("client-a", "10.0.0.1", "/api/items"), [12]),
        (("client-b", "10.0.0.1", "/api/items"), [13]),
    ]


def test_overlapping_windows_include_events_in_each_containing_window() -> None:
    windows = list(
        iter_event_windows(
            [event(55), event(59)],
            config=WindowConfig(
                duration=timedelta(seconds=60),
                overlap=timedelta(seconds=10),
            ),
        )
    )

    assert len(windows) == 2
    assert [[item.sequence_no for item in window.events] for window in windows] == [
        [56, 60],
        [56, 60],
    ]
    assert windows[0].start_time.isoformat() == "2026-07-01T12:00:00+00:00"
    assert windows[1].start_time.isoformat() == "2026-07-01T12:00:50+00:00"


def test_window_ids_are_stable() -> None:
    config = WindowConfig(duration=timedelta(seconds=10))
    first = list(iter_event_windows([event(1), event(2)], config=config))
    second = list(iter_event_windows([event(1), event(2)], config=config))
    assert [window.window_id for window in first] == [window.window_id for window in second]


def test_out_of_order_events_are_rejected() -> None:
    with pytest.raises(ValueError, match="ordered by timestamp"):
        list(
            iter_event_windows(
                [event(2), event(1)],
                config=WindowConfig(duration=timedelta(seconds=10)),
            )
        )


@pytest.mark.parametrize(
    ("duration", "overlap"),
    [
        (0, 0),
        (10, -1),
        (10, 10),
        (10, 11),
    ],
)
def test_invalid_window_configuration_is_rejected(duration: int, overlap: int) -> None:
    with pytest.raises(ValueError, match="window"):
        WindowConfig(
            duration=timedelta(seconds=duration),
            overlap=timedelta(seconds=overlap),
        )


def test_event_window_contract_rejects_empty_windows() -> None:
    with pytest.raises(ValueError, match="at least one event"):
        EventWindow(
            window_id="window-empty",
            entity_key=("client-a",),
            start_time=datetime(2026, 7, 1, tzinfo=UTC),
            end_time=datetime(2026, 7, 1, tzinfo=UTC) + timedelta(seconds=10),
            events=(),
        )
