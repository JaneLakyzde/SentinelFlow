"""Deterministic candidate detection pipeline."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable
from datetime import timedelta
from pathlib import Path

from sentinelflow.core.models import AuditEvent, Candidate
from sentinelflow.core.windowing import WindowConfig, iter_event_windows
from sentinelflow.detectors.config import ParameterEnumerationConfig
from sentinelflow.detectors.deduplication import deduplicate_candidates
from sentinelflow.detectors.enumeration import detect_parameter_enumeration
from sentinelflow.features.parameters import parameter_window_features


def parameter_enumeration_candidates(
    events: Iterable[AuditEvent],
    *,
    parameter_path: str,
    config: ParameterEnumerationConfig,
) -> list[Candidate]:
    """Detect and stably deduplicate candidates across overlapping windows."""
    window_config = WindowConfig(
        duration=timedelta(seconds=config.duration_seconds),
        overlap=timedelta(seconds=config.overlap_seconds),
    )
    candidates: list[Candidate] = []
    for window in iter_event_windows(events, config=window_config):
        features = parameter_window_features(window, parameter_path=parameter_path)
        if features.observed_value_count == 0:
            continue
        candidate = detect_parameter_enumeration(window, features, config=config)
        if candidate is not None:
            candidates.append(candidate)
    return deduplicate_candidates(candidates)


def write_candidates_jsonl(candidates: Iterable[Candidate], output: Path | str) -> None:
    """Atomically write candidates as UTF-8 JSONL."""
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            for candidate in candidates:
                payload = json.dumps(
                    candidate.to_dict(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                stream.write(f"{payload}\n")
        assert temporary_path is not None
        temporary_path.replace(output_path)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
