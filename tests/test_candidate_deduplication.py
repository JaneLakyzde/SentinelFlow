"""Tests for stable overlapping-window candidate deduplication."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sentinelflow.core.models import Candidate, CandidateEvidence, EvidenceType
from sentinelflow.detectors.deduplication import deduplicate_candidates


def candidate(
    candidate_id: str,
    sequence_numbers: tuple[int, ...],
    window_id: str,
    *,
    actor: str = "client-a",
) -> Candidate:
    start = datetime(2026, 7, 1, 12, tzinfo=UTC)
    return Candidate(
        candidate_id=candidate_id,
        suggested_category="parameter_enumeration",
        parameter_path="body.posid",
        entity=(("actor", actor), ("source_ip", "10.0.0.1"), ("path", "/items")),
        start_time=start + timedelta(seconds=min(sequence_numbers)),
        end_time=start + timedelta(seconds=max(sequence_numbers)),
        sequence_numbers=sequence_numbers,
        source_window_ids=(window_id,),
        triggered_rule_ids=("parameter-enumeration.cardinality",),
        evidence=(
            CandidateEvidence(
                evidence_type=EvidenceType.PARAMETER_CARDINALITY,
                metric="distinct_value_count",
                actual=len(sequence_numbers),
                threshold=5,
                comparison="gte",
                sequence_numbers=sequence_numbers,
            ),
        ),
        feature_values=(("distinct_value_count", len(sequence_numbers)),),
        detector_config_version="1.0",
        context_complete=True,
        closest_benign_pattern=None,
        baseline_version=None,
    )


def test_merges_transitively_overlapping_candidates() -> None:
    candidates = [
        candidate("candidate-a", (1, 2, 3), "window-a"),
        candidate("candidate-b", (3, 4, 5), "window-b"),
        candidate("candidate-c", (5, 6, 7), "window-c"),
    ]

    result = deduplicate_candidates(candidates)

    assert len(result) == 1
    assert result[0].sequence_numbers == (1, 2, 3, 4, 5, 6, 7)
    assert result[0].source_window_ids == ("window-a", "window-b", "window-c")
    assert dict(result[0].feature_values)["merged_candidate_count"] == 3


def test_deduplication_is_independent_of_input_order() -> None:
    first = candidate("candidate-a", (1, 2, 3, 4, 5), "window-a")
    second = candidate("candidate-b", (3, 4, 5, 6, 7), "window-b")

    forward = deduplicate_candidates([first, second])
    reverse = deduplicate_candidates([second, first])

    assert [item.to_dict() for item in forward] == [item.to_dict() for item in reverse]


def test_keeps_disjoint_and_different_entity_candidates_separate() -> None:
    first = candidate("candidate-a", (1, 2, 3), "window-a")
    disjoint = candidate("candidate-b", (10, 11, 12), "window-b")
    other_actor = replace(
        candidate("candidate-c", (2, 3, 4), "window-c"),
        entity=(("actor", "client-b"), ("source_ip", "10.0.0.1"), ("path", "/items")),
    )

    result = deduplicate_candidates([other_actor, disjoint, first])

    assert len(result) == 3
    assert {item.candidate_id for item in result} == {
        "candidate-a",
        "candidate-b",
        "candidate-c",
    }
