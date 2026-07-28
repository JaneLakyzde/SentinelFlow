"""Skill-constrained LLM candidate review."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sentinelflow.core.models import Candidate
from sentinelflow.llm.client import LLMClient
from sentinelflow.llm.prompts import build_review_request
from sentinelflow.llm.schemas import CandidateReview, LLMOutputError, parse_candidate_review
from sentinelflow.llm.skill import SkillBundle


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
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    correction: str | None = None
    last_error: LLMOutputError | None = None
    for _ in range(max_attempts):
        request = build_review_request(
            candidate,
            skill=skill,
            event_projection=event_projection,
            normal_context=normal_context,
            correction=correction,
        )
        raw_output = client.generate(request)
        try:
            return parse_candidate_review(
                raw_output,
                candidate=candidate,
                skill_version=skill.version,
            )
        except LLMOutputError as error:
            last_error = error
            correction = str(error)
    assert last_error is not None
    raise last_error
