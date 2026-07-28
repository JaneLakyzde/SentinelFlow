"""Skill-constrained LLM candidate review."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sentinelflow.core.models import Candidate
from sentinelflow.llm.client import LLMClient, LLMResponse
from sentinelflow.llm.prompts import build_review_request
from sentinelflow.llm.schemas import CandidateReview, LLMOutputError, parse_candidate_review
from sentinelflow.llm.skill import SkillBundle


@dataclass(frozen=True, slots=True)
class CandidateReviewRun:
    """A validated decision and all provider attempts used to obtain it."""

    review: CandidateReview
    responses: tuple[LLMResponse, ...]


class ReviewAttemptsExhaustedError(LLMOutputError):
    """Raised when all bounded model outputs fail local validation."""

    def __init__(self, message: str, responses: tuple[LLMResponse, ...]) -> None:
        super().__init__(message)
        self.responses = responses


def review_candidate(
    candidate: Candidate,
    *,
    client: LLMClient,
    skill: SkillBundle,
    event_projection: Sequence[Mapping[str, object]] = (),
    normal_context: Mapping[str, object] | None = None,
    max_attempts: int = 3,
) -> CandidateReview:
    """Review a candidate, retrying only bounded schema/evidence failures."""
    return review_candidate_run(
        candidate,
        client=client,
        skill=skill,
        event_projection=event_projection,
        normal_context=normal_context,
        max_attempts=max_attempts,
    ).review


def review_candidate_run(
    candidate: Candidate,
    *,
    client: LLMClient,
    skill: SkillBundle,
    event_projection: Sequence[Mapping[str, object]] = (),
    normal_context: Mapping[str, object] | None = None,
    max_attempts: int = 3,
) -> CandidateReviewRun:
    """Review a candidate and retain safe provider metadata for every attempt."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    correction: str | None = None
    last_error: LLMOutputError | None = None
    responses: list[LLMResponse] = []
    for _ in range(max_attempts):
        request = build_review_request(
            candidate,
            skill=skill,
            event_projection=event_projection,
            normal_context=normal_context,
            correction=correction,
        )
        response = client.generate(request)
        responses.append(response)
        try:
            return CandidateReviewRun(
                review=parse_candidate_review(
                    response.content,
                    candidate=candidate,
                    skill_version=skill.version,
                ),
                responses=tuple(responses),
            )
        except LLMOutputError as error:
            invalidate = getattr(client, "invalidate", None)
            if callable(invalidate):
                invalidate(request)
            last_error = error
            correction = str(error)
    assert last_error is not None
    raise ReviewAttemptsExhaustedError(str(last_error), tuple(responses)) from last_error
