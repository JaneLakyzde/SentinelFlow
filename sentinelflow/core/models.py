"""Immutable data contracts used by SentinelFlow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
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
