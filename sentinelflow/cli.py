"""Command-line interface for SentinelFlow."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from sentinelflow.core.errors import InputError
from sentinelflow.core.jsonl import JsonlEventReader
from sentinelflow.core.summary import EventSummary
from sentinelflow.core.windowing import WindowConfig, iter_event_windows
from sentinelflow.features.parameters import parameter_window_features


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sentinelflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="validate and summarize an API audit JSONL file",
    )
    inspect_parser.add_argument("--input", type=Path, required=True, help="input JSONL file")
    inspect_parser.add_argument(
        "--skip-invalid",
        action="store_true",
        help="skip malformed or invalid rows and report their count",
    )

    profile_parser = subparsers.add_parser(
        "profile-parameter",
        help="emit deterministic per-window features for one body parameter",
    )
    profile_parser.add_argument("--input", type=Path, required=True, help="input JSONL file")
    profile_parser.add_argument(
        "--parameter",
        required=True,
        help="nested body field, for example body.posid",
    )
    profile_parser.add_argument(
        "--window-seconds",
        type=int,
        default=60,
        help="window duration in seconds (default: 60)",
    )
    profile_parser.add_argument(
        "--overlap-seconds",
        type=int,
        default=10,
        help="window overlap in seconds (default: 10)",
    )
    profile_parser.add_argument(
        "--skip-invalid",
        action="store_true",
        help="skip malformed or invalid rows",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "inspect":
        reader = JsonlEventReader(args.input, skip_invalid=args.skip_invalid)
        try:
            summary = EventSummary.from_events(reader)
        except (InputError, OSError) as error:
            parser.exit(2, f"error: {error}\n")
        print(summary.render(invalid_rows=reader.invalid_rows))
        return 0

    if args.command == "profile-parameter":
        try:
            config = WindowConfig(
                duration=timedelta(seconds=args.window_seconds),
                overlap=timedelta(seconds=args.overlap_seconds),
            )
            reader = JsonlEventReader(args.input, skip_invalid=args.skip_invalid)
            for window in iter_event_windows(reader, config=config):
                features = parameter_window_features(
                    window,
                    parameter_path=args.parameter,
                )
                if features.observed_value_count == 0:
                    continue
                payload = features.to_dict()
                payload["start_time"] = window.start_time.isoformat()
                payload["end_time"] = window.end_time.isoformat()
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            if reader.invalid_rows:
                print(
                    f"warning: skipped invalid rows: {reader.invalid_rows}",
                    file=sys.stderr,
                )
        except (InputError, OSError, ValueError) as error:
            parser.exit(2, f"error: {error}\n")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2
