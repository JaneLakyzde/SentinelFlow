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
from sentinelflow.detectors.config import load_parameter_enumeration_config
from sentinelflow.detectors.pipeline import (
    parameter_enumeration_candidates,
    write_candidates_jsonl,
)
from sentinelflow.evaluation.parameter_enumeration import (
    evaluate_parameter_enumeration,
    write_evaluation_report,
)
from sentinelflow.features.parameters import parameter_window_features
from sentinelflow.llm.cache import CachedLLMClient
from sentinelflow.llm.deepseek import DeepSeekClient, LLMServiceError
from sentinelflow.llm.pipeline import (
    load_normal_context,
    project_candidate_events,
    write_review_records,
)
from sentinelflow.llm.review import ReviewAttemptsExhaustedError, review_candidate_run
from sentinelflow.llm.schemas import LLMOutputError
from sentinelflow.llm.settings import LLMConfigurationError, LLMSettings
from sentinelflow.llm.skill import default_skill_path, load_skill_bundle

_PACKAGE_ENUMERATION_CONFIG = (
    Path(__file__).resolve().parent / "resources" / "configs" / "parameter-enumeration.yaml"
)
_REPOSITORY_ENUMERATION_CONFIG = (
    Path(__file__).resolve().parents[1] / "configs" / "parameter-enumeration.yaml"
)
DEFAULT_ENUMERATION_CONFIG = (
    _PACKAGE_ENUMERATION_CONFIG
    if _PACKAGE_ENUMERATION_CONFIG.is_file()
    else _REPOSITORY_ENUMERATION_CONFIG
)


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

    detect_parser = subparsers.add_parser(
        "detect-parameter-enumeration",
        help="write deduplicated high-recall candidates to JSONL",
    )
    detect_parser.add_argument("--input", type=Path, required=True, help="input JSONL file")
    detect_parser.add_argument(
        "--parameter",
        required=True,
        help="nested body field, for example body.posid",
    )
    detect_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_ENUMERATION_CONFIG,
        help="parameter-enumeration YAML thresholds",
    )
    detect_parser.add_argument(
        "--output",
        type=Path,
        default=Path("candidates.jsonl"),
        help="candidate JSONL output (default: candidates.jsonl)",
    )
    detect_parser.add_argument(
        "--skip-invalid",
        action="store_true",
        help="skip malformed or invalid rows",
    )

    review_parser = subparsers.add_parser(
        "review-parameter-enumeration",
        help="detect and review parameter-enumeration candidates with an LLM",
    )
    review_parser.add_argument("--input", type=Path, required=True, help="input JSONL file")
    review_parser.add_argument(
        "--parameter",
        required=True,
        help="nested body field, for example body.posid",
    )
    review_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_ENUMERATION_CONFIG,
        help="parameter-enumeration YAML thresholds",
    )
    review_parser.add_argument(
        "--output",
        type=Path,
        default=Path("reviews.jsonl"),
        help="review JSONL output (default: reviews.jsonl)",
    )
    review_parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="LLM dotenv file (default: .env)",
    )
    review_parser.add_argument(
        "--skill",
        type=Path,
        default=default_skill_path(),
        help="versioned API-security Skill directory",
    )
    review_parser.add_argument(
        "--normal-context",
        type=Path,
        help="optional trusted normal-context JSON object",
    )
    review_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="disable the local content-addressed LLM response cache",
    )
    review_parser.add_argument(
        "--skip-invalid",
        action="store_true",
        help="skip malformed or invalid rows",
    )

    evaluate_parser = subparsers.add_parser(
        "evaluate-parameter-enumeration",
        help="evaluate candidates and LLM reviews against isolated Ground Truth",
    )
    evaluate_parser.add_argument(
        "--ground-truth",
        type=Path,
        required=True,
        help="evaluator-only Ground Truth JSONL",
    )
    evaluate_parser.add_argument(
        "--candidates",
        type=Path,
        required=True,
        help="candidate JSONL produced without Ground Truth access",
    )
    evaluate_parser.add_argument(
        "--reviews",
        type=Path,
        help="optional LLM review JSONL",
    )
    evaluate_parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON report path; otherwise print to stdout",
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

    if args.command == "detect-parameter-enumeration":
        try:
            config = load_parameter_enumeration_config(args.config)
            reader = JsonlEventReader(args.input, skip_invalid=args.skip_invalid)
            candidates = parameter_enumeration_candidates(
                reader,
                parameter_path=args.parameter,
                config=config,
            )
            write_candidates_jsonl(candidates, args.output)
            if reader.invalid_rows:
                print(
                    f"warning: skipped invalid rows: {reader.invalid_rows}",
                    file=sys.stderr,
                )
        except (InputError, OSError, ValueError) as error:
            parser.exit(2, f"error: {error}\n")
        return 0

    if args.command == "review-parameter-enumeration":
        try:
            settings = LLMSettings.from_env(args.env_file)
            detector_config = load_parameter_enumeration_config(args.config)
            skill = load_skill_bundle(args.skill)
            normal_context = load_normal_context(args.normal_context)
            reader = JsonlEventReader(args.input, skip_invalid=args.skip_invalid)
            candidates = parameter_enumeration_candidates(
                reader,
                parameter_path=args.parameter,
                config=detector_config,
            )
            projections = project_candidate_events(
                JsonlEventReader(args.input, skip_invalid=args.skip_invalid),
                candidates,
            )
        except (
            InputError,
            json.JSONDecodeError,
            LLMConfigurationError,
            OSError,
            ValueError,
        ) as error:
            parser.exit(2, f"error: {error}\n")

        provider_client = DeepSeekClient(settings)
        client = (
            provider_client
            if args.no_cache
            else CachedLLMClient(provider_client, settings.cache_directory)
        )
        records: list[dict[str, object]] = []
        reviewed = 0
        failed = 0
        cache_hits = 0
        for candidate in candidates:
            candidate_context = {
                **normal_context,
                "candidate_context_complete": candidate.context_complete,
                "closest_benign_pattern": candidate.closest_benign_pattern,
            }
            try:
                run = review_candidate_run(
                    candidate,
                    client=client,
                    skill=skill,
                    event_projection=projections.get(candidate.candidate_id, ()),
                    normal_context=candidate_context,
                    max_attempts=settings.max_retries + 1,
                )
                metadata = [response.to_metadata_dict() for response in run.responses]
                cache_hits += sum(response.cached for response in run.responses)
                records.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "status": "reviewed",
                        "review": run.review.to_dict(),
                        "llm_attempts": metadata,
                    }
                )
                reviewed += 1
            except ReviewAttemptsExhaustedError as error:
                records.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "status": "error",
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "llm_attempts": [
                            response.to_metadata_dict() for response in error.responses
                        ],
                    }
                )
                failed += 1
            except (LLMOutputError, LLMServiceError, OSError) as error:
                records.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "status": "error",
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                )
                failed += 1
        try:
            write_review_records(records, args.output)
        except OSError as error:
            parser.exit(2, f"error: {error}\n")
        if reader.invalid_rows:
            print(
                f"warning: skipped invalid rows: {reader.invalid_rows}",
                file=sys.stderr,
            )
        print(
            f"candidates={len(candidates)} reviewed={reviewed} "
            f"failed={failed} cache_hits={cache_hits}",
            file=sys.stderr,
        )
        return 1 if failed else 0

    if args.command == "evaluate-parameter-enumeration":
        try:
            report = evaluate_parameter_enumeration(
                args.ground_truth,
                args.candidates,
                args.reviews,
            )
            if args.output is None:
                print(
                    json.dumps(
                        report.to_dict(),
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                write_evaluation_report(report, args.output)
        except (OSError, ValueError) as error:
            parser.exit(2, f"error: {error}\n")
        return 0

    parser.error(f"unknown command: {args.command}")
