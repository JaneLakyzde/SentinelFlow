"""Tests for parameter-enumeration threshold configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinelflow.detectors.config import load_parameter_enumeration_config

ROOT = Path(__file__).parents[1]


def test_repository_threshold_config_loads() -> None:
    config = load_parameter_enumeration_config(ROOT / "configs/parameter-enumeration.yaml")

    assert config.version == "1.1"
    assert config.duration_seconds == 60
    assert config.overlap_seconds == 40
    assert config.minimum_distinct_values == 5
    assert config.failure_statuses == (400, 401, 403, 404, 410)
    assert "page" in config.pagination_parameter_names


def test_config_rejects_unknown_keys(tmp_path: Path) -> None:
    source = (ROOT / "configs/parameter-enumeration.yaml").read_text(encoding="utf-8")
    path = tmp_path / "thresholds.yaml"
    path.write_text(
        source.replace('version: "1.1"', 'version: "1.1"\ntypo: true'),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"unknown.*typo"):
        load_parameter_enumeration_config(path)


def test_config_rejects_invalid_ratio(tmp_path: Path) -> None:
    source = (ROOT / "configs/parameter-enumeration.yaml").read_text(encoding="utf-8")
    path = tmp_path / "thresholds.yaml"
    path.write_text(
        source.replace("minimum_sequence_ratio: 0.6", "minimum_sequence_ratio: 1.2"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="minimum_sequence_ratio"):
        load_parameter_enumeration_config(path)


def test_config_rejects_overlap_equal_to_duration(tmp_path: Path) -> None:
    source = (ROOT / "configs/parameter-enumeration.yaml").read_text(encoding="utf-8")
    path = tmp_path / "thresholds.yaml"
    path.write_text(
        source.replace("overlap_seconds: 40", "overlap_seconds: 60"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="overlap_seconds"):
        load_parameter_enumeration_config(path)
