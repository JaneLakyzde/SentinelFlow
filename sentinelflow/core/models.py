"""Immutable data contracts used by SentinelFlow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """A normalized API audit event with its source record attached."""

    sequence_no: int
    timestamp: datetime
    request_id: str
    actor: str
    source_ip: str
    method: str
    path: str
    body: Mapping[str, Any]
    http_status: int | None
    response_code: str | None
    issued_sid: str | None
    raw_record: Mapping[str, Any]
    raw_line_number: int


@dataclass(frozen=True, slots=True)
class EventWindow:
    """A deterministic, half-open time window containing related events."""

    window_id: str
    entity_key: tuple[str, ...]
    start_time: datetime
    end_time: datetime
    events: tuple[AuditEvent, ...]

    def __post_init__(self) -> None:
        if not self.window_id:
            raise ValueError("window_id must be non-empty")
        if not self.entity_key or any(not part for part in self.entity_key):
            raise ValueError("entity_key must contain non-empty strings")
        if self.start_time.tzinfo is None or self.start_time.utcoffset() is None:
            raise ValueError("window start_time must include a timezone")
        if self.end_time.tzinfo is None or self.end_time.utcoffset() is None:
            raise ValueError("window end_time must include a timezone")
        if self.start_time >= self.end_time:
            raise ValueError("window start_time must precede end_time")
        if not self.events:
            raise ValueError("window must contain at least one event")

        previous = self.events[0]
        for event in self.events:
            if not self.start_time <= event.timestamp < self.end_time:
                raise ValueError("window event timestamp is outside the half-open window")
            if event.timestamp < previous.timestamp:
                raise ValueError("window events must be ordered by timestamp")
            previous = event


class EvidenceType(StrEnum):
    """Closed vocabulary for deterministic candidate evidence."""

    PARAMETER_CARDINALITY = "parameter_cardinality"
    CONSECUTIVE_SEQUENCE = "consecutive_sequence"
    FIXED_STEP_SEQUENCE = "fixed_step_sequence"
    RANDOM_HIGH_CARDINALITY = "random_high_cardinality"
    RESPONSE_DISTRIBUTION = "response_distribution"
    STABLE_CONTEXT = "stable_context"
    RAPID_ACTIVITY = "rapid_activity"
    BENIGN_PAGINATION = "benign_pagination"


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """One measured observation supporting or qualifying a candidate."""

    evidence_type: EvidenceType
    metric: str
    actual: int | float | str | bool
    threshold: int | float | str | bool | None
    comparison: str
    sequence_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.metric:
            raise ValueError("evidence metric must be non-empty")
        if self.comparison not in {"eq", "gte", "lte", "context"}:
            raise ValueError("unsupported evidence comparison")
        if not self.sequence_numbers or any(number <= 0 for number in self.sequence_numbers):
            raise ValueError("evidence must reference positive sequence numbers")
        if tuple(sorted(set(self.sequence_numbers))) != self.sequence_numbers:
            raise ValueError("evidence sequence_numbers must be sorted and unique")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        payload = asdict(self)
        payload["evidence_type"] = self.evidence_type.value
        payload["sequence_numbers"] = list(self.sequence_numbers)
        return payload


@dataclass(frozen=True, slots=True)
class Candidate:
    """A high-recall anomaly candidate; it is not a security alert."""

    candidate_id: str
    suggested_category: str
    parameter_path: str
    entity: tuple[tuple[str, str], ...]
    start_time: datetime
    end_time: datetime
    sequence_numbers: tuple[int, ...]
    source_window_ids: tuple[str, ...]
    triggered_rule_ids: tuple[str, ...]
    evidence: tuple[CandidateEvidence, ...]
    feature_values: tuple[tuple[str, int | float | str | bool | None], ...]
    detector_config_version: str
    context_complete: bool
    closest_benign_pattern: str | None
    baseline_version: str | None

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id must be non-empty")
        if not self.suggested_category:
            raise ValueError("suggested_category must be non-empty")
        if not self.parameter_path:
            raise ValueError("parameter_path must be non-empty")
        if not self.entity or any(not key or not value for key, value in self.entity):
            raise ValueError("candidate entity must contain non-empty keys and values")
        if len({key for key, _ in self.entity}) != len(self.entity):
            raise ValueError("candidate entity keys must be unique")
        if self.start_time.tzinfo is None or self.start_time.utcoffset() is None:
            raise ValueError("candidate start_time must include a timezone")
        if self.end_time.tzinfo is None or self.end_time.utcoffset() is None:
            raise ValueError("candidate end_time must include a timezone")
        if self.start_time > self.end_time:
            raise ValueError("candidate start_time cannot follow end_time")
        if not self.sequence_numbers or any(number <= 0 for number in self.sequence_numbers):
            raise ValueError("candidate must reference positive sequence numbers")
        if tuple(sorted(set(self.sequence_numbers))) != self.sequence_numbers:
            raise ValueError("candidate sequence_numbers must be sorted and unique")
        if not self.source_window_ids or any(not item for item in self.source_window_ids):
            raise ValueError("candidate must reference source windows")
        if not self.triggered_rule_ids or any(not item for item in self.triggered_rule_ids):
            raise ValueError("candidate must contain triggered rules")
        if not self.evidence:
            raise ValueError("candidate must contain evidence")
        candidate_sequences = set(self.sequence_numbers)
        if any(
            not set(item.sequence_numbers).issubset(candidate_sequences) for item in self.evidence
        ):
            raise ValueError("candidate evidence references sequence numbers outside candidate")
        if len({key for key, _ in self.feature_values}) != len(self.feature_values):
            raise ValueError("candidate feature keys must be unique")
        if not self.detector_config_version:
            raise ValueError("detector_config_version must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-ready representation."""
        return {
            "candidate_id": self.candidate_id,
            "suggested_category": self.suggested_category,
            "parameter_path": self.parameter_path,
            "entity": dict(self.entity),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "sequence_numbers": list(self.sequence_numbers),
            "source_window_ids": list(self.source_window_ids),
            "triggered_rule_ids": list(self.triggered_rule_ids),
            "evidence": [item.to_dict() for item in self.evidence],
            "features": dict(self.feature_values),
            "detector_config_version": self.detector_config_version,
            "context_complete": self.context_complete,
            "closest_benign_pattern": self.closest_benign_pattern,
            "baseline_version": self.baseline_version,
        }
