"""Tests for high-recall candidate data contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sentinelflow.core.models import Candidate, CandidateEvidence, EvidenceType


def candidate() -> Candidate:
    return Candidate(
        candidate_id="candidate-abc123",
        suggested_category="parameter_enumeration",
        parameter_path="body.posid",
        entity=(
            ("actor", "client-a"),
            ("source_ip", "10.0.0.1"),
            ("path", "/items"),
        ),
        start_time=datetime(2026, 7, 1, 12, tzinfo=UTC),
        end_time=datetime(2026, 7, 1, 12, 0, 3, tzinfo=UTC),
        sequence_numbers=(1, 2, 3, 4),
        source_window_ids=("window-one",),
        triggered_rule_ids=("parameter-enumeration.sequence",),
        evidence=(
            CandidateEvidence(
                evidence_type=EvidenceType.CONSECUTIVE_SEQUENCE,
                metric="consecutive_ratio",
                actual=1.0,
                threshold=0.6,
                comparison="gte",
                sequence_numbers=(1, 2, 3, 4),
            ),
        ),
        feature_values=(("distinct_value_count", 4), ("duration_seconds", 3.0)),
        detector_config_version="1.0",
        context_complete=True,
        closest_benign_pattern=None,
        baseline_version=None,
    )


def test_candidate_serializes_closed_evidence_vocabulary() -> None:
    payload = candidate().to_dict()

    assert payload["candidate_id"] == "candidate-abc123"
    assert payload["entity"] == {
        "actor": "client-a",
        "source_ip": "10.0.0.1",
        "path": "/items",
    }
    assert payload["sequence_numbers"] == [1, 2, 3, 4]
    assert payload["evidence"][0]["evidence_type"] == "consecutive_sequence"
    assert payload["features"]["distinct_value_count"] == 4


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"candidate_id": ""}, "candidate_id"),
        ({"sequence_numbers": ()}, "sequence"),
        ({"sequence_numbers": (2, 1)}, "sorted"),
        ({"triggered_rule_ids": ()}, "triggered"),
        ({"evidence": ()}, "evidence"),
        ({"detector_config_version": ""}, "detector_config_version"),
    ],
)
def test_candidate_rejects_incomplete_contract(
    changes: dict[str, object],
    message: str,
) -> None:
    values = {field: getattr(candidate(), field) for field in candidate().__dataclass_fields__}
    values.update(changes)

    with pytest.raises(ValueError, match=message):
        Candidate(**values)  # type: ignore[arg-type]


def test_evidence_rejects_unknown_comparison() -> None:
    with pytest.raises(ValueError, match="comparison"):
        CandidateEvidence(
            evidence_type=EvidenceType.PARAMETER_CARDINALITY,
            metric="distinct_value_count",
            actual=5,
            threshold=4,
            comparison="approximately",
            sequence_numbers=(1,),
        )


def test_candidate_rejects_evidence_outside_candidate_sequences() -> None:
    values = {field: getattr(candidate(), field) for field in candidate().__dataclass_fields__}
    values["evidence"] = (
        CandidateEvidence(
            evidence_type=EvidenceType.PARAMETER_CARDINALITY,
            metric="distinct_value_count",
            actual=5,
            threshold=4,
            comparison="gte",
            sequence_numbers=(1, 99),
        ),
    )

    with pytest.raises(ValueError, match="outside"):
        Candidate(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"entity": (("actor", "one"), ("actor", "two"))},
        {"feature_values": (("count", 1), ("count", 2))},
    ],
)
def test_candidate_rejects_duplicate_mapping_keys(changes: dict[str, object]) -> None:
    values = {field: getattr(candidate(), field) for field in candidate().__dataclass_fields__}
    values.update(changes)

    with pytest.raises(ValueError, match="keys must be unique"):
        Candidate(**values)  # type: ignore[arg-type]
