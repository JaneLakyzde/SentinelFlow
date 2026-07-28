"""Ground-Truth-isolated parameter-enumeration evaluation tests."""

from __future__ import annotations

import json
from pathlib import Path

from sentinelflow.evaluation.parameter_enumeration import evaluate_parameter_enumeration


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_evaluator_reports_candidate_and_llm_precision_gain(tmp_path: Path) -> None:
    truth_path = tmp_path / "truth.jsonl"
    candidates_path = tmp_path / "candidates.jsonl"
    reviews_path = tmp_path / "reviews.jsonl"
    write_jsonl(
        truth_path,
        [
            {
                "sequence_no": 1,
                "is_anomaly": True,
                "category": "parameter_enumeration",
            },
            {
                "sequence_no": 2,
                "is_anomaly": True,
                "category": "parameter_enumeration",
            },
            {"sequence_no": 3, "is_anomaly": False, "category": "normal"},
            {"sequence_no": 4, "is_anomaly": False, "category": "normal"},
            {
                "sequence_no": 5,
                "is_anomaly": False,
                "category": "legitimate_pagination",
            },
            {
                "sequence_no": 6,
                "is_anomaly": False,
                "category": "legitimate_pagination",
            },
        ],
    )
    write_jsonl(
        candidates_path,
        [
            {"candidate_id": "target", "sequence_numbers": [1, 2, 3]},
            {"candidate_id": "pagination", "sequence_numbers": [5, 6]},
        ],
    )
    write_jsonl(
        reviews_path,
        [
            {
                "candidate_id": "target",
                "status": "reviewed",
                "review": {"decision": "alert", "sequence_numbers": [1, 2]},
            },
            {
                "candidate_id": "pagination",
                "status": "reviewed",
                "review": {"decision": "benign"},
            },
        ],
    )

    report = evaluate_parameter_enumeration(
        truth_path,
        candidates_path,
        reviews_path,
    ).to_dict()

    candidate = report["candidate"]
    llm = report["llm_review"]
    assert isinstance(candidate, dict)
    assert isinstance(llm, dict)
    assert candidate["precision"] == 0.5
    assert candidate["episode_recall"] == 1
    assert candidate["pagination_event_false_positive_rate"] == 1
    assert llm["precision"] == 1
    assert llm["precision_gain"] == 0.5
    assert llm["pagination_event_false_positive_rate"] == 0
