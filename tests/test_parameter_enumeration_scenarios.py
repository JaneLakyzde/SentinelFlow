"""End-to-end deterministic baseline scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinelflow.core.jsonl import JsonlEventReader
from sentinelflow.detectors.config import load_parameter_enumeration_config
from sentinelflow.detectors.enumeration import FIXED_STEP_RULE, RANDOM_RULE, SEQUENCE_RULE
from sentinelflow.detectors.pipeline import (
    parameter_enumeration_candidates,
    write_candidates_jsonl,
)

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "parameter_enumeration"
CONFIG = load_parameter_enumeration_config(ROOT / "configs" / "parameter-enumeration.yaml")


@pytest.mark.parametrize(
    ("filename", "parameter", "expected_rule"),
    [
        ("consecutive.jsonl", "body.posid", SEQUENCE_RULE),
        ("fixed_step.jsonl", "body.resource_id", FIXED_STEP_RULE),
        ("random_high_cardinality.jsonl", "body.resource_id", RANDOM_RULE),
    ],
)
def test_attack_scenarios_each_produce_one_candidate(
    filename: str,
    parameter: str,
    expected_rule: str,
) -> None:
    candidates = parameter_enumeration_candidates(
        JsonlEventReader(FIXTURES / filename),
        parameter_path=parameter,
        config=CONFIG,
    )

    assert len(candidates) == 1
    assert expected_rule in candidates[0].triggered_rule_ids
    assert candidates[0].suggested_category == "parameter_enumeration"


def test_legitimate_pagination_produces_no_candidate() -> None:
    candidates = parameter_enumeration_candidates(
        JsonlEventReader(FIXTURES / "legitimate_pagination.jsonl"),
        parameter_path="body.page",
        config=CONFIG,
    )

    assert candidates == []


def test_candidate_writer_preserves_existing_output_on_failure(tmp_path: Path) -> None:
    output = tmp_path / "candidates.jsonl"
    output.write_text("existing\n", encoding="utf-8")

    def failing_candidates():
        yield parameter_enumeration_candidates(
            JsonlEventReader(FIXTURES / "consecutive.jsonl"),
            parameter_path="body.posid",
            config=CONFIG,
        )[0]
        raise RuntimeError("injected write failure")

    with pytest.raises(RuntimeError, match="injected"):
        write_candidates_jsonl(failing_candidates(), output)

    assert output.read_text(encoding="utf-8") == "existing\n"
    assert list(tmp_path.glob(".candidates.jsonl.*.tmp")) == []
