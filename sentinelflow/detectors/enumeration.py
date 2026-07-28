"""High-recall deterministic parameter-enumeration candidate detection."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from sentinelflow.core.models import (
    AuditEvent,
    Candidate,
    CandidateEvidence,
    EventWindow,
    EvidenceType,
)
from sentinelflow.detectors.config import ParameterEnumerationConfig
from sentinelflow.features.parameters import ParameterWindowFeatures

CATEGORY = "parameter_enumeration"
CARDINALITY_RULE = "parameter-enumeration.cardinality"
SEQUENCE_RULE = "parameter-enumeration.consecutive-sequence"
FIXED_STEP_RULE = "parameter-enumeration.fixed-step"
RANDOM_RULE = "parameter-enumeration.random-high-cardinality"
FAILURE_RULE = "parameter-enumeration.failure-distribution"


def detect_parameter_enumeration(
    window: EventWindow,
    features: ParameterWindowFeatures,
    *,
    config: ParameterEnumerationConfig,
) -> Candidate | None:
    """Return one high-recall candidate for a qualifying window."""
    if features.window_id != window.window_id:
        raise ValueError("features and window must have the same window_id")
    if features.duration_seconds > config.duration_seconds:
        raise ValueError("feature duration exceeds the configured window duration")
    if features.distinct_value_count < config.minimum_distinct_values:
        return None

    parameter_name = features.parameter_path.rsplit(".", maxsplit=1)[-1].lower()
    is_pagination = parameter_name in config.pagination_parameter_names
    if is_pagination and config.suppress_pagination_parameters:
        return None

    sequence_ratios = [
        value
        for value in (
            features.consecutive_ratio,
            features.ascending_ratio,
            features.descending_ratio,
        )
        if value is not None
    ]
    sequence_ratio = (
        max(sequence_ratios)
        if features.numeric_value_count >= config.minimum_numeric_values and sequence_ratios
        else 0.0
    )
    fixed_step_ratio = features.fixed_step_ratio or 0.0
    systematic_step_ratio = max(features.consecutive_ratio or 0.0, fixed_step_ratio)
    failure_count = sum(
        count for status, count in features.status_counts if status in config.failure_statuses
    )
    failure_ratio = (
        failure_count / features.observed_value_count if features.observed_value_count else 0.0
    )

    triggered = [CARDINALITY_RULE]
    pattern_evidence: list[CandidateEvidence] = []
    if sequence_ratio >= config.minimum_sequence_ratio:
        triggered.append(SEQUENCE_RULE)
        pattern_evidence.append(
            _evidence(
                EvidenceType.CONSECUTIVE_SEQUENCE,
                "sequence_ratio",
                sequence_ratio,
                config.minimum_sequence_ratio,
                features.sequence_numbers,
            )
        )
    if (
        features.numeric_value_count >= config.minimum_numeric_values
        and fixed_step_ratio >= config.minimum_fixed_step_ratio
    ):
        triggered.append(FIXED_STEP_RULE)
        pattern_evidence.append(
            _evidence(
                EvidenceType.FIXED_STEP_SEQUENCE,
                "fixed_step_ratio",
                fixed_step_ratio,
                config.minimum_fixed_step_ratio,
                features.sequence_numbers,
            )
        )
    if (
        features.distinct_value_count >= config.minimum_random_distinct_values
        and systematic_step_ratio <= config.maximum_random_sequence_ratio
    ):
        triggered.append(RANDOM_RULE)
        pattern_evidence.append(
            _evidence(
                EvidenceType.RANDOM_HIGH_CARDINALITY,
                "distinct_value_count",
                features.distinct_value_count,
                config.minimum_random_distinct_values,
                features.sequence_numbers,
            )
        )
    if failure_ratio >= config.minimum_failure_ratio:
        triggered.append(FAILURE_RULE)
        pattern_evidence.append(
            _evidence(
                EvidenceType.RESPONSE_DISTRIBUTION,
                "failure_ratio",
                failure_ratio,
                config.minimum_failure_ratio,
                features.sequence_numbers,
            )
        )
    if not pattern_evidence:
        return None

    first_event, last_event = _events_for_sequences(window, features.sequence_numbers)
    evidence = [
        _evidence(
            EvidenceType.PARAMETER_CARDINALITY,
            "distinct_value_count",
            features.distinct_value_count,
            config.minimum_distinct_values,
            features.sequence_numbers,
        ),
        *pattern_evidence,
        _evidence(
            EvidenceType.STABLE_CONTEXT,
            "stable_context_ratio",
            features.stable_context_ratio,
            config.minimum_stable_context_ratio,
            features.sequence_numbers,
            comparison="context",
        ),
        _evidence(
            EvidenceType.RAPID_ACTIVITY,
            "duration_seconds",
            features.duration_seconds,
            config.duration_seconds,
            features.sequence_numbers,
            comparison="lte",
        ),
    ]
    closest_benign_pattern = "pagination" if is_pagination else None
    if is_pagination:
        evidence.append(
            _evidence(
                EvidenceType.BENIGN_PAGINATION,
                "pagination_parameter",
                parameter_name,
                True,
                features.sequence_numbers,
                comparison="context",
            )
        )

    feature_values: tuple[tuple[str, int | float | str | bool | None], ...] = (
        ("event_count", features.event_count),
        ("observed_value_count", features.observed_value_count),
        ("distinct_value_count", features.distinct_value_count),
        ("numeric_value_count", features.numeric_value_count),
        ("numeric_span", features.numeric_span),
        ("ascending_ratio", features.ascending_ratio),
        ("descending_ratio", features.descending_ratio),
        ("consecutive_ratio", features.consecutive_ratio),
        ("fixed_step_ratio", features.fixed_step_ratio),
        ("entropy_bits", features.entropy_bits),
        ("duration_seconds", features.duration_seconds),
        ("stable_context_ratio", features.stable_context_ratio),
        ("failure_ratio", failure_ratio),
    )
    entity_names = ("actor", "source_ip", "path")
    entity = tuple(zip(entity_names, window.entity_key, strict=False))
    candidate_id = _candidate_id(
        entity,
        features.parameter_path,
        features.sequence_numbers,
        triggered,
    )
    return Candidate(
        candidate_id=candidate_id,
        suggested_category=CATEGORY,
        parameter_path=features.parameter_path,
        entity=entity,
        start_time=first_event.timestamp,
        end_time=last_event.timestamp,
        sequence_numbers=tuple(sorted(set(features.sequence_numbers))),
        source_window_ids=(window.window_id,),
        triggered_rule_ids=tuple(triggered),
        evidence=tuple(evidence),
        feature_values=feature_values,
        detector_config_version=config.version,
        context_complete=True,
        closest_benign_pattern=closest_benign_pattern,
        baseline_version=config.baseline_version,
    )


def _evidence(
    evidence_type: EvidenceType,
    metric: str,
    actual: int | float | str | bool,
    threshold: int | float | str | bool | None,
    sequence_numbers: tuple[int, ...],
    *,
    comparison: str = "gte",
) -> CandidateEvidence:
    return CandidateEvidence(
        evidence_type=evidence_type,
        metric=metric,
        actual=actual,
        threshold=threshold,
        comparison=comparison,
        sequence_numbers=sequence_numbers,
    )


def _events_for_sequences(
    window: EventWindow,
    sequence_numbers: tuple[int, ...],
) -> tuple[AuditEvent, AuditEvent]:
    selected = [event for event in window.events if event.sequence_no in sequence_numbers]
    if not selected:
        raise ValueError("features must reference events in the window")
    return selected[0], selected[-1]


def _candidate_id(
    entity: tuple[tuple[str, str], ...],
    parameter_path: str,
    sequence_numbers: tuple[int, ...],
    rule_ids: Iterable[str],
) -> str:
    material = repr(
        (
            entity,
            parameter_path,
            tuple(sorted(set(sequence_numbers))),
            tuple(sorted(rule_ids)),
        )
    ).encode()
    return f"candidate-{hashlib.sha256(material).hexdigest()[:16]}"
