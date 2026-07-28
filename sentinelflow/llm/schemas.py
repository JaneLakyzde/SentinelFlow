"""Strict local validation for untrusted LLM review output."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sentinelflow.core.models import Candidate, EvidenceType


class LLMOutputError(ValueError):
    """Raised when model output violates the local review contract."""


class ReviewDecision(StrEnum):
    ALERT = "alert"
    BENIGN = "benign"
    ABSTAIN = "abstain"
    OUT_OF_SCOPE = "out_of_scope"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class ReviewEvidence:
    evidence_type: EvidenceType
    metric: str
    actual: int | float | str | bool
    observation: str
    sequence_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_type, EvidenceType):
            raise ValueError("review evidence_type must be an EvidenceType")
        if not isinstance(self.metric, str) or not self.metric.strip():
            raise ValueError("review evidence metric must be a non-empty string")
        if not isinstance(self.actual, int | float | str | bool):
            raise ValueError("review evidence actual must be a scalar")
        if not isinstance(self.observation, str) or not self.observation.strip():
            raise ValueError("review evidence observation must be a non-empty string")
        if not self.sequence_numbers or any(
            isinstance(number, bool) or not isinstance(number, int) or number <= 0
            for number in self.sequence_numbers
        ):
            raise ValueError("review evidence must reference positive sequence numbers")
        if tuple(sorted(set(self.sequence_numbers))) != self.sequence_numbers:
            raise ValueError("review evidence sequence_numbers must be sorted and unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_type": self.evidence_type.value,
            "metric": self.metric,
            "actual": self.actual,
            "observation": self.observation,
            "sequence_numbers": list(self.sequence_numbers),
        }


@dataclass(frozen=True, slots=True)
class CandidateReview:
    candidate_id: str
    decision: ReviewDecision
    category: str | None
    severity: Severity | None
    confidence: float
    sequence_numbers: tuple[int, ...]
    evidence: tuple[ReviewEvidence, ...]
    explanation: str
    benign_alternative: str
    uncertainty_reasons: tuple[str, ...]
    skill_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id:
            raise ValueError("candidate_id must be a non-empty string")
        if not isinstance(self.decision, ReviewDecision):
            raise ValueError("decision must be a ReviewDecision")
        if self.category is not None and not isinstance(self.category, str):
            raise ValueError("category must be a string or null")
        if self.severity is not None and not isinstance(self.severity, Severity):
            raise ValueError("severity must be a Severity or null")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, int | float):
            raise ValueError("confidence must be a number")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if any(
            isinstance(number, bool) or not isinstance(number, int) or number <= 0
            for number in self.sequence_numbers
        ):
            raise ValueError("sequence_numbers must contain positive integers")
        if tuple(sorted(set(self.sequence_numbers))) != self.sequence_numbers:
            raise ValueError("sequence_numbers must be sorted and unique")
        if any(not isinstance(item, ReviewEvidence) for item in self.evidence):
            raise ValueError("evidence must contain ReviewEvidence values")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise ValueError("explanation must be a non-empty string")
        if not isinstance(self.benign_alternative, str) or not self.benign_alternative.strip():
            raise ValueError("benign_alternative must be a non-empty string")
        if any(
            not isinstance(reason, str) or not reason.strip() for reason in self.uncertainty_reasons
        ):
            raise ValueError("uncertainty_reasons must contain non-empty strings")
        if not isinstance(self.skill_version, str) or not self.skill_version:
            raise ValueError("skill_version must be a non-empty string")

        if self.decision is ReviewDecision.ALERT:
            if self.category != "parameter_enumeration":
                raise ValueError("alert category must be parameter_enumeration")
            if self.severity is None or not self.sequence_numbers or not self.evidence:
                raise ValueError("alert requires severity, sequence numbers, and evidence")
        elif self.category is not None or self.severity is not None:
            raise ValueError("non-alert decisions require null category and severity")
        if self.decision is ReviewDecision.ABSTAIN and not self.uncertainty_reasons:
            raise ValueError("abstain requires uncertainty_reasons")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision.value,
            "category": self.category,
            "severity": self.severity.value if self.severity is not None else None,
            "confidence": self.confidence,
            "sequence_numbers": list(self.sequence_numbers),
            "evidence": [item.to_dict() for item in self.evidence],
            "explanation": self.explanation,
            "benign_alternative": self.benign_alternative,
            "uncertainty_reasons": list(self.uncertainty_reasons),
            "skill_version": self.skill_version,
        }


REVIEW_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "candidate_id",
        "decision",
        "category",
        "severity",
        "confidence",
        "sequence_numbers",
        "evidence",
        "explanation",
        "benign_alternative",
        "uncertainty_reasons",
    ],
    "properties": {
        "candidate_id": {"type": "string", "minLength": 1},
        "decision": {
            "type": "string",
            "enum": [item.value for item in ReviewDecision],
        },
        "category": {
            "type": ["string", "null"],
            "enum": ["parameter_enumeration", None],
        },
        "severity": {
            "type": ["string", "null"],
            "enum": [*[item.value for item in Severity], None],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "sequence_numbers": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1},
            "uniqueItems": True,
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "evidence_type",
                    "metric",
                    "actual",
                    "observation",
                    "sequence_numbers",
                ],
                "properties": {
                    "evidence_type": {
                        "type": "string",
                        "enum": [item.value for item in EvidenceType],
                    },
                    "metric": {"type": "string", "minLength": 1},
                    "actual": {"type": ["number", "string", "boolean"]},
                    "observation": {"type": "string", "minLength": 1},
                    "sequence_numbers": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 1},
                        "minItems": 1,
                        "uniqueItems": True,
                    },
                },
            },
        },
        "explanation": {"type": "string", "minLength": 1},
        "benign_alternative": {"type": "string", "minLength": 1},
        "uncertainty_reasons": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
}

_REQUIRED_KEYS = set(REVIEW_SCHEMA["required"])  # type: ignore[arg-type]


def parse_candidate_review(
    raw_output: str,
    *,
    candidate: Candidate,
    skill_version: str,
) -> CandidateReview:
    """Parse and validate a model response against candidate evidence."""
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as error:
        raise LLMOutputError(f"model output is not valid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise LLMOutputError("model output must be a JSON object")
    actual_keys = set(payload)
    if actual_keys != _REQUIRED_KEYS:
        raise LLMOutputError("model output has missing or unknown fields")
    if payload["candidate_id"] != candidate.candidate_id:
        raise LLMOutputError("candidate_id does not match the reviewed candidate")

    decision = _enum(ReviewDecision, payload["decision"], "decision")
    category = payload["category"]
    if category is not None and not isinstance(category, str):
        raise LLMOutputError("category must be a string or null")
    severity = (
        None if payload["severity"] is None else _enum(Severity, payload["severity"], "severity")
    )
    confidence = _confidence(payload["confidence"])
    sequence_numbers = _sequence_numbers(payload["sequence_numbers"], "sequence_numbers")
    candidate_sequences = set(candidate.sequence_numbers)
    if not set(sequence_numbers).issubset(candidate_sequences):
        raise LLMOutputError("review cites sequence numbers outside the candidate")

    evidence_payload = payload["evidence"]
    if not isinstance(evidence_payload, list):
        raise LLMOutputError("evidence must be a list")
    evidence = tuple(_parse_evidence(item, candidate_sequences) for item in evidence_payload)
    explanation = _non_empty_string(payload["explanation"], "explanation")
    benign_alternative = _non_empty_string(payload["benign_alternative"], "benign_alternative")
    uncertainty_reasons = _string_list(
        payload["uncertainty_reasons"],
        "uncertainty_reasons",
    )

    if decision is ReviewDecision.ALERT:
        if category != "parameter_enumeration":
            raise LLMOutputError("alert category must be parameter_enumeration")
        if severity is None or not sequence_numbers or not evidence:
            raise LLMOutputError("alert requires severity, sequence numbers, and evidence")
    elif category is not None or severity is not None:
        raise LLMOutputError("non-alert decisions require null category and severity")
    if decision is ReviewDecision.ABSTAIN and not uncertainty_reasons:
        raise LLMOutputError("abstain requires uncertainty_reasons")

    for item in evidence:
        matching = [
            candidate_item
            for candidate_item in candidate.evidence
            if candidate_item.evidence_type is item.evidence_type
            and candidate_item.metric == item.metric
            and _same_scalar(candidate_item.actual, item.actual)
            and set(item.sequence_numbers).issubset(candidate_item.sequence_numbers)
        ]
        if not matching:
            raise LLMOutputError("review evidence does not match candidate evidence")

    return CandidateReview(
        candidate_id=candidate.candidate_id,
        decision=decision,
        category=category,
        severity=severity,
        confidence=confidence,
        sequence_numbers=sequence_numbers,
        evidence=evidence,
        explanation=explanation,
        benign_alternative=benign_alternative,
        uncertainty_reasons=uncertainty_reasons,
        skill_version=skill_version,
    )


def _parse_evidence(value: object, candidate_sequences: set[int]) -> ReviewEvidence:
    if not isinstance(value, dict) or set(value) != {
        "evidence_type",
        "metric",
        "actual",
        "observation",
        "sequence_numbers",
    }:
        raise LLMOutputError("each evidence item must have exactly the required fields")
    evidence_type = _enum(EvidenceType, value["evidence_type"], "evidence_type")
    metric = _non_empty_string(value["metric"], "evidence metric")
    actual = value["actual"]
    if not isinstance(actual, int | float | str | bool):
        raise LLMOutputError("evidence actual must be a scalar")
    observation = _non_empty_string(value["observation"], "evidence observation")
    sequence_numbers = _sequence_numbers(
        value["sequence_numbers"],
        "evidence sequence_numbers",
    )
    if not sequence_numbers or not set(sequence_numbers).issubset(candidate_sequences):
        raise LLMOutputError("evidence cites sequence numbers outside the candidate")
    return ReviewEvidence(evidence_type, metric, actual, observation, sequence_numbers)


def _enum(enum_type, value: object, location: str):
    if not isinstance(value, str):
        raise LLMOutputError(f"{location} must be a string")
    try:
        return enum_type(value)
    except ValueError as error:
        raise LLMOutputError(f"{location} has an unsupported value") from error


def _confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise LLMOutputError("confidence must be a number")
    result = float(value)
    if not 0 <= result <= 1:
        raise LLMOutputError("confidence must be between 0 and 1")
    return result


def _sequence_numbers(value: object, location: str) -> tuple[int, ...]:
    if not isinstance(value, list) or any(
        isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in value
    ):
        raise LLMOutputError(f"{location} must contain positive integers")
    result = tuple(value)
    if tuple(sorted(set(result))) != result:
        raise LLMOutputError(f"{location} must be sorted and unique")
    return result


def _non_empty_string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LLMOutputError(f"{location} must be a non-empty string")
    return value


def _string_list(value: object, location: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise LLMOutputError(f"{location} must be a list of non-empty strings")
    return tuple(value)


def _same_scalar(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, int | float) and isinstance(right, int | float):
        return float(left) == float(right)
    return type(left) is type(right) and left == right
