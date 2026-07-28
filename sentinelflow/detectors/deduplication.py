"""Stable deduplication for candidates emitted by overlapping windows."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from sentinelflow.core.models import Candidate, CandidateEvidence


def deduplicate_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Merge connected overlapping candidates with order-independent output."""
    grouped: dict[
        tuple[str, str, tuple[tuple[str, str], ...], str, str | None],
        list[Candidate],
    ] = defaultdict(list)
    for candidate in candidates:
        grouped[
            (
                candidate.suggested_category,
                candidate.parameter_path,
                candidate.entity,
                candidate.detector_config_version,
                candidate.baseline_version,
            )
        ].append(candidate)

    merged: list[Candidate] = []
    for group_key in sorted(grouped):
        remaining = sorted(grouped[group_key], key=_candidate_sort_key)
        while remaining:
            component = [remaining.pop(0)]
            component_sequences = set(component[0].sequence_numbers)
            changed = True
            while changed:
                changed = False
                retained: list[Candidate] = []
                for candidate in remaining:
                    if component_sequences.intersection(candidate.sequence_numbers):
                        component.append(candidate)
                        component_sequences.update(candidate.sequence_numbers)
                        changed = True
                    else:
                        retained.append(candidate)
                remaining = retained
            merged.append(_merge_component(component))
    return sorted(merged, key=_candidate_sort_key)


def _merge_component(component: list[Candidate]) -> Candidate:
    ordered = sorted(component, key=_candidate_sort_key)
    if len(ordered) == 1:
        return ordered[0]

    representative = min(
        ordered,
        key=lambda item: (-len(item.sequence_numbers), _candidate_sort_key(item)),
    )
    sequence_numbers = tuple(
        sorted({number for candidate in ordered for number in candidate.sequence_numbers})
    )
    source_window_ids = tuple(
        sorted({window for candidate in ordered for window in candidate.source_window_ids})
    )
    triggered_rule_ids = tuple(
        sorted({rule for candidate in ordered for rule in candidate.triggered_rule_ids})
    )
    evidence = tuple(
        sorted(
            {
                _evidence_key(item): item for candidate in ordered for item in candidate.evidence
            }.values(),
            key=_evidence_key,
        )
    )
    feature_values = (
        *representative.feature_values,
        ("merged_candidate_count", len(ordered)),
    )
    benign_patterns = sorted(
        {
            candidate.closest_benign_pattern
            for candidate in ordered
            if candidate.closest_benign_pattern is not None
        }
    )
    return Candidate(
        candidate_id=_merged_id(representative, sequence_numbers, source_window_ids),
        suggested_category=representative.suggested_category,
        parameter_path=representative.parameter_path,
        entity=representative.entity,
        start_time=min(candidate.start_time for candidate in ordered),
        end_time=max(candidate.end_time for candidate in ordered),
        sequence_numbers=sequence_numbers,
        source_window_ids=source_window_ids,
        triggered_rule_ids=triggered_rule_ids,
        evidence=evidence,
        feature_values=feature_values,
        detector_config_version=representative.detector_config_version,
        context_complete=all(candidate.context_complete for candidate in ordered),
        closest_benign_pattern=";".join(benign_patterns) or None,
        baseline_version=representative.baseline_version,
    )


def _candidate_sort_key(candidate: Candidate):
    return (
        candidate.start_time,
        candidate.end_time,
        candidate.entity,
        candidate.parameter_path,
        candidate.sequence_numbers,
        candidate.candidate_id,
    )


def _evidence_key(evidence: CandidateEvidence):
    return (
        evidence.evidence_type.value,
        evidence.metric,
        str(evidence.actual),
        str(evidence.threshold),
        evidence.comparison,
        evidence.sequence_numbers,
    )


def _merged_id(
    representative: Candidate,
    sequence_numbers: tuple[int, ...],
    source_window_ids: tuple[str, ...],
) -> str:
    material = repr(
        (
            representative.suggested_category,
            representative.parameter_path,
            representative.entity,
            sequence_numbers,
            source_window_ids,
        )
    ).encode()
    return f"candidate-{hashlib.sha256(material).hexdigest()[:16]}"
