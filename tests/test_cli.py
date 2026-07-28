"""CLI tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinelflow.cli import DEFAULT_ENUMERATION_CONFIG, main


def test_inspect_outputs_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "events.jsonl"
    rows = [
        {
            "timestamp": "2026-07-01T12:00:00Z",
            "request_id": "one",
            "actor": "client-a",
            "source_ip": "10.0.0.1",
            "method": "get",
            "path": "/one?token=secret",
            "body": {},
            "http_status": 200,
        },
        {
            "timestamp": "2026-07-01T12:01:00+00:00",
            "request_id": "two",
            "actor": "client-b",
            "source_ip": "10.0.0.2",
            "method": "POST",
            "path": "/two/",
            "body": {},
            "http_status": 404,
        },
    ]
    path.write_text("".join(f"{json.dumps(row)}\n" for row in rows), encoding="utf-8")

    assert main(["inspect", "--input", str(path)]) == 0
    output = capsys.readouterr().out
    assert "events: 2" in output
    assert "actors: 2" in output
    assert "sources: 2" in output
    assert "paths: 2" in output
    assert "status codes: 200: 1, 404: 1" in output
    assert "invalid rows: 0" in output


def test_inspect_missing_file_exits_cleanly(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["inspect", "--input", str(tmp_path / "missing.jsonl")])
    assert caught.value.code == 2


def test_profile_parameter_outputs_json_features(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "events.jsonl"
    rows = [
        {
            "timestamp": f"2026-07-01T12:00:0{index}Z",
            "request_id": f"req-{index}",
            "actor": "client-a",
            "source_ip": "10.0.0.1",
            "method": "GET",
            "path": "/items",
            "body": {"resource": {"id": 100 + index}},
            "http_status": 404,
        }
        for index in range(3)
    ]
    path.write_text("".join(f"{json.dumps(row)}\n" for row in rows), encoding="utf-8")

    assert (
        main(
            [
                "profile-parameter",
                "--input",
                str(path),
                "--parameter",
                "body.resource.id",
                "--window-seconds",
                "10",
                "--overlap-seconds",
                "0",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["distinct_value_count"] == 3
    assert payload["consecutive_ratio"] == 1
    assert payload["sequence_numbers"] == [1, 2, 3]
    assert payload["status_counts"] == {"404": 3}


def test_profile_parameter_rejects_invalid_window(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text("", encoding="utf-8")

    with pytest.raises(SystemExit) as caught:
        main(
            [
                "profile-parameter",
                "--input",
                str(path),
                "--parameter",
                "body.posid",
                "--window-seconds",
                "10",
                "--overlap-seconds",
                "10",
            ]
        )

    assert caught.value.code == 2


def test_profile_parameter_reports_skipped_rows(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "mixed.jsonl"
    valid = {
        "timestamp": "2026-07-01T12:00:00Z",
        "request_id": "req-1",
        "actor": "client-a",
        "source_ip": "10.0.0.1",
        "method": "GET",
        "path": "/items",
        "body": {"posid": 100},
        "http_status": 200,
    }
    path.write_text(f"{json.dumps(valid)}\n{{bad json}}\n", encoding="utf-8")

    assert (
        main(
            [
                "profile-parameter",
                "--input",
                str(path),
                "--parameter",
                "body.posid",
                "--window-seconds",
                "10",
                "--overlap-seconds",
                "0",
                "--skip-invalid",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert json.loads(captured.out)["observed_value_count"] == 1
    assert captured.err == "warning: skipped invalid rows: 1\n"


def test_detect_parameter_enumeration_writes_deduplicated_candidates(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "events.jsonl"
    output_path = tmp_path / "candidates.jsonl"
    rows = [
        {
            "timestamp": f"2026-07-01T12:00:0{index}Z",
            "request_id": f"req-{index}",
            "actor": "client-a",
            "source_ip": "10.0.0.1",
            "method": "GET",
            "path": "/items",
            "body": {"posid": 100 + index, "tenant": "tenant-a"},
            "http_status": 404 if index > 2 else 200,
        }
        for index in range(8)
    ]
    input_path.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "detect-parameter-enumeration",
                "--input",
                str(input_path),
                "--parameter",
                "body.posid",
                "--config",
                str(DEFAULT_ENUMERATION_CONFIG),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["suggested_category"] == "parameter_enumeration"
    assert payload["sequence_numbers"] == list(range(1, 9))
    assert len(payload["source_window_ids"]) >= 1
    assert payload["evidence"]


def test_detect_parameter_enumeration_creates_empty_output_for_pagination(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "events.jsonl"
    output_path = tmp_path / "candidates.jsonl"
    rows = [
        {
            "timestamp": f"2026-07-01T12:00:0{index}Z",
            "request_id": f"req-{index}",
            "actor": "client-a",
            "source_ip": "10.0.0.1",
            "method": "GET",
            "path": "/items",
            "body": {"page": index + 1, "page_size": 20},
            "http_status": 200,
        }
        for index in range(8)
    ]
    input_path.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "detect-parameter-enumeration",
                "--input",
                str(input_path),
                "--parameter",
                "body.page",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    assert output_path.read_text(encoding="utf-8") == ""


def test_detect_parameter_enumeration_rejects_missing_config(tmp_path: Path) -> None:
    input_path = tmp_path / "events.jsonl"
    input_path.write_text("", encoding="utf-8")

    with pytest.raises(SystemExit) as caught:
        main(
            [
                "detect-parameter-enumeration",
                "--input",
                str(input_path),
                "--parameter",
                "body.posid",
                "--config",
                str(tmp_path / "missing.yaml"),
            ]
        )

    assert caught.value.code == 2
