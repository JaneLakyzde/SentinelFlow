"""Ground-Truth-isolated evaluation for parameter-enumeration predictions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TARGET_CATEGORY = "parameter_enumeration"
PAGINATION_CATEGORY = "legitimate_pagination"


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Candidate and LLM metrics at candidate, episode, and request levels."""

    payload: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return self.payload


def evaluate_parameter_enumeration(
    ground_truth_path: Path | str,
    candidates_path: Path | str,
    reviews_path: Path | str | None = None,
) -> EvaluationReport:
    """Evaluate predictions without exposing Ground Truth to the audit pipeline."""
    truth_rows = _read_jsonl(Path(ground_truth_path))
    candidate_rows = _read_jsonl(Path(candidates_path))
    review_rows = _read_jsonl(Path(reviews_path)) if reviews_path is not None else []
    truth = _truth_by_sequence(truth_rows)
    candidates = _candidate_sequences(candidate_rows, truth)
    alert_sequences, review_counts = _review_alerts(review_rows, candidates)
    alert_candidate_ids = set(alert_sequences)

    target_events = {
        sequence_no for sequence_no, row in truth.items() if row.get("category") == TARGET_CATEGORY
    }
    pagination_events = {
        sequence_no
        for sequence_no, row in truth.items()
        if row.get("category") == PAGINATION_CATEGORY
    }
    normal_events = {
        sequence_no for sequence_no, row in truth.items() if not bool(row.get("is_anomaly"))
    }
    target_episodes = _contiguous_episodes(target_events)
    candidate_coverage = set().union(*candidates.values()) if candidates else set()
    alert_coverage = set().union(*alert_sequences.values()) if alert_sequences else set()
    true_candidate_ids = {
        candidate_id
        for candidate_id, sequences in candidates.items()
        if sequences.intersection(target_events)
    }
    false_candidate_ids = set(candidates) - true_candidate_ids
    true_alert_ids = alert_candidate_ids.intersection(true_candidate_ids)
    false_alert_ids = alert_candidate_ids - true_candidate_ids

    candidate_precision = _ratio(len(true_candidate_ids), len(candidates))
    llm_precision = _ratio(len(true_alert_ids), len(alert_candidate_ids))
    return EvaluationReport(
        {
            "ground_truth": {
                "event_count": len(truth),
                "target_event_count": len(target_events),
                "target_episode_count": len(target_episodes),
                "normal_event_count": len(normal_events),
                "pagination_event_count": len(pagination_events),
            },
            "candidate": {
                "count": len(candidates),
                "true_positive_count": len(true_candidate_ids),
                "false_positive_count": len(false_candidate_ids),
                "precision": candidate_precision,
                "episode_recall": _episode_recall(target_episodes, candidate_coverage),
                "event_recall": _coverage_rate(target_events, candidate_coverage),
                "normal_event_false_positive_rate": _coverage_rate(
                    normal_events, candidate_coverage
                ),
                "pagination_event_false_positive_rate": _coverage_rate(
                    pagination_events, candidate_coverage
                ),
            },
            "llm_review": {
                **review_counts,
                "alert_count": len(alert_candidate_ids),
                "true_positive_count": len(true_alert_ids),
                "false_positive_count": len(false_alert_ids),
                "precision": llm_precision,
                "episode_recall": _episode_recall(target_episodes, alert_coverage),
                "event_recall": _coverage_rate(target_events, alert_coverage),
                "normal_event_false_positive_rate": _coverage_rate(normal_events, alert_coverage),
                "pagination_event_false_positive_rate": _coverage_rate(
                    pagination_events, alert_coverage
                ),
                "precision_gain": (
                    llm_precision - candidate_precision
                    if llm_precision is not None and candidate_precision is not None
                    else None
                ),
            },
        }
    )


def write_evaluation_report(report: EvaluationReport, output: Path | str) -> None:
    """Write one deterministic, human-readable JSON report."""
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from error
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(value)
    return rows


def _truth_by_sequence(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        sequence_no = row.get("sequence_no")
        if (
            isinstance(sequence_no, bool)
            or not isinstance(sequence_no, int)
            or sequence_no < 1
            or sequence_no in result
        ):
            raise ValueError("Ground Truth sequence_no values must be unique positive integers")
        result[sequence_no] = row
    return result


def _candidate_sequences(
    rows: list[dict[str, Any]],
    truth: dict[int, dict[str, Any]],
) -> dict[str, set[int]]:
    result: dict[str, set[int]] = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        raw_sequences = row.get("sequence_numbers")
        if not isinstance(candidate_id, str) or not candidate_id or candidate_id in result:
            raise ValueError("candidate_id values must be unique non-empty strings")
        if not isinstance(raw_sequences, list) or any(
            isinstance(item, bool) or not isinstance(item, int) or item not in truth
            for item in raw_sequences
        ):
            raise ValueError(f"candidate {candidate_id} references invalid sequence numbers")
        result[candidate_id] = set(raw_sequences)
    return result


def _review_alerts(
    rows: list[dict[str, Any]],
    candidates: dict[str, set[int]],
) -> tuple[dict[str, set[int]], dict[str, int]]:
    alerts: dict[str, set[int]] = {}
    counts = {
        "reviewed_count": 0,
        "error_count": 0,
        "benign_count": 0,
        "abstain_count": 0,
        "out_of_scope_count": 0,
    }
    seen: set[str] = set()
    for row in rows:
        candidate_id = row.get("candidate_id")
        if (
            not isinstance(candidate_id, str)
            or candidate_id not in candidates
            or candidate_id in seen
        ):
            raise ValueError("reviews must reference unique known candidate_id values")
        seen.add(candidate_id)
        if row.get("status") == "error":
            counts["error_count"] += 1
            continue
        review = row.get("review")
        if row.get("status") != "reviewed" or not isinstance(review, dict):
            raise ValueError("review records must have reviewed or error status")
        counts["reviewed_count"] += 1
        decision = review.get("decision")
        if decision == "alert":
            raw_sequences = review.get("sequence_numbers")
            if not isinstance(raw_sequences, list) or any(
                isinstance(item, bool)
                or not isinstance(item, int)
                or item not in candidates[candidate_id]
                for item in raw_sequences
            ):
                raise ValueError("alert review references invalid sequence numbers")
            alerts[candidate_id] = set(raw_sequences)
        elif decision in {"benign", "abstain", "out_of_scope"}:
            counts[f"{decision}_count"] += 1
        else:
            raise ValueError("review decision is unsupported")
    return alerts, counts


def _contiguous_episodes(sequences: set[int]) -> list[set[int]]:
    episodes: list[set[int]] = []
    current: set[int] = set()
    previous: int | None = None
    for sequence_no in sorted(sequences):
        if previous is not None and sequence_no != previous + 1:
            episodes.append(current)
            current = set()
        current.add(sequence_no)
        previous = sequence_no
    if current:
        episodes.append(current)
    return episodes


def _episode_recall(episodes: list[set[int]], coverage: set[int]) -> float | None:
    if not episodes:
        return None
    return sum(bool(episode.intersection(coverage)) for episode in episodes) / len(episodes)


def _coverage_rate(expected: set[int], coverage: set[int]) -> float | None:
    return _ratio(len(expected.intersection(coverage)), len(expected))


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
