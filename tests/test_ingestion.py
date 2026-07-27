"""Tests for JSONL ingestion and normalization."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sentinelflow.core.errors import EventValidationError, JsonlDecodeError
from sentinelflow.core.jsonl import JsonlEventReader
from sentinelflow.core.normalization import normalize_event, normalize_path, parse_timestamp


def raw_event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "timestamp": "2026-07-01T20:00:01.123+08:00",
        "request_id": " req-1 ",
        "actor": " client-a ",
        "source_ip": " 10.0.0.1 ",
        "method": " post ",
        "path": "api//items/?page=2#part",
        "body": {"nested": ["value"]},
        "http_status": "200",
        "response_code": " OK ",
        "issued_sid": "",
    }
    event.update(overrides)
    return event


def write_jsonl(path: Path, rows: list[object]) -> None:
    path.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )


def test_normal_event_is_normalized_and_source_is_preserved() -> None:
    event = normalize_event(raw_event(), source="events.jsonl", line_number=7)

    assert event.sequence_no == 7
    assert event.timestamp == datetime(2026, 7, 1, 12, 0, 1, 123000, tzinfo=UTC)
    assert event.request_id == "req-1"
    assert event.actor == "client-a"
    assert event.source_ip == "10.0.0.1"
    assert event.method == "POST"
    assert event.path == "/api/items"
    assert event.http_status == 200
    assert event.response_code == "OK"
    assert event.issued_sid is None
    assert event.raw_line_number == 7
    assert event.raw_record["method"] == " post "


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-07-01T12:00:00Z", datetime(2026, 7, 1, 12, tzinfo=UTC)),
        ("2026-07-01T20:00:00+08:00", datetime(2026, 7, 1, 12, tzinfo=UTC)),
        ("2026-07-01T07:00:00-05:00", datetime(2026, 7, 1, 12, tzinfo=UTC)),
    ],
)
def test_timestamp_offsets_are_converted_to_utc(value: str, expected: datetime) -> None:
    assert parse_timestamp(value) == expected


@pytest.mark.parametrize("value", ["", "not-a-time", "2026-07-01T12:00:00"])
def test_invalid_or_naive_timestamp_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="timestamp"):
        parse_timestamp(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/", "/"),
        ("/api/items/?x=1", "/api/items"),
        ("api//items", "/api/items"),
        ("https://example.test/api/items/?x=1#fragment", "/api/items"),
    ],
)
def test_path_normalization(value: str, expected: str) -> None:
    assert normalize_path(value) == expected


@pytest.mark.parametrize(
    "field",
    ["timestamp", "request_id", "actor", "source_ip", "method", "path"],
)
def test_missing_required_field_has_a_located_error(field: str) -> None:
    raw = raw_event()
    del raw[field]

    with pytest.raises(EventValidationError) as caught:
        normalize_event(raw, source="fixture.jsonl", line_number=9)

    assert str(caught.value).startswith("fixture.jsonl:9:")
    assert f"'{field}'" in str(caught.value)


def test_body_null_defaults_to_empty_mapping() -> None:
    event = normalize_event(raw_event(body=None), source="events.jsonl", line_number=1)
    assert dict(event.body) == {}


def test_event_nested_data_is_immutable() -> None:
    event = normalize_event(raw_event(), source="events.jsonl", line_number=1)
    with pytest.raises(TypeError):
        event.body["new"] = "value"  # type: ignore[index]
    assert event.body["nested"] == ("value",)


def test_reader_streams_rows_and_uses_physical_line_numbers(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    write_jsonl(path, [raw_event(request_id="one"), raw_event(request_id="two")])

    events = list(JsonlEventReader(path))

    assert [event.request_id for event in events] == ["one", "two"]
    assert [event.sequence_no for event in events] == [1, 2]
    assert [event.raw_line_number for event in events] == [1, 2]


def test_existing_sequence_number_is_retained(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    write_jsonl(path, [raw_event(sequence_no=42)])
    assert next(iter(JsonlEventReader(path))).sequence_no == 42


@pytest.mark.parametrize("bad_line", ["{bad json}\n", "\n", "[]\n"])
def test_invalid_json_rows_report_file_and_line(tmp_path: Path, bad_line: str) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(raw_event()) + "\n" + bad_line, encoding="utf-8")

    with pytest.raises(JsonlDecodeError) as caught:
        list(JsonlEventReader(path))

    assert str(caught.value).startswith(f"{path}:2:")


def test_skip_invalid_continues_and_counts_all_bad_rows(tmp_path: Path) -> None:
    path = tmp_path / "mixed.jsonl"
    path.write_text(
        json.dumps(raw_event(request_id="one"))
        + "\n{bad}\n"
        + json.dumps(raw_event(request_id="two", timestamp=None))
        + "\n"
        + json.dumps(raw_event(request_id="three"))
        + "\n",
        encoding="utf-8",
    )
    reader = JsonlEventReader(path, skip_invalid=True)

    events = list(reader)

    assert [event.request_id for event in events] == ["one", "three"]
    assert [event.raw_line_number for event in events] == [1, 4]
    assert reader.invalid_rows == 2


def test_invalid_utf8_reports_physical_line(tmp_path: Path) -> None:
    path = tmp_path / "invalid-encoding.jsonl"
    path.write_bytes(json.dumps(raw_event()).encode() + b"\n\xff\n")

    with pytest.raises(JsonlDecodeError) as caught:
        list(JsonlEventReader(path))

    assert str(caught.value).startswith(f"{path}:2:")
    assert "UTF-8" in str(caught.value)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_numbers_are_rejected(tmp_path: Path, constant: str) -> None:
    path = tmp_path / "non-finite.jsonl"
    payload = json.dumps(raw_event())
    path.write_text(payload[:-1] + f', "duration_ms": {constant}}}\n', encoding="utf-8")

    with pytest.raises(JsonlDecodeError, match="non-finite"):
        list(JsonlEventReader(path))
