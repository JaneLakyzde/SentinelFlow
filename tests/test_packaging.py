"""Tests for runtime resources required by installed wheels."""

from __future__ import annotations

import tomllib
from pathlib import Path

from sentinelflow.cli import DEFAULT_ENUMERATION_CONFIG

ROOT = Path(__file__).parents[1]


def test_default_detector_config_exists() -> None:
    assert DEFAULT_ENUMERATION_CONFIG.is_file()


def test_wheel_force_includes_config_and_skill() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    included = project["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]

    assert included["configs/parameter-enumeration.yaml"].startswith("sentinelflow/resources/")
    assert included["domains/api_security/skills/audit-api-security/SKILL.md"].startswith(
        "sentinelflow/resources/"
    )
