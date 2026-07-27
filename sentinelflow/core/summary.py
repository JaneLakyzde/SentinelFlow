"""Bounded-memory summary statistics for normalized events."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from sentinelflow.core.models import AuditEvent


@dataclass(slots=True)
class EventSummary:
    """Aggregate only the cardinalities and counts needed by ``inspect``."""

    events: int = 0
    actors: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    paths: set[str] = field(default_factory=set)
    status_codes: Counter[int | None] = field(default_factory=Counter)
    start_time: datetime | None = None
    end_time: datetime | None = None

    def add(self, event: AuditEvent) -> None:
        self.events += 1
        self.actors.add(event.actor)
        self.sources.add(event.source_ip)
        self.paths.add(event.path)
        self.status_codes[event.http_status] += 1
        if self.start_time is None or event.timestamp < self.start_time:
            self.start_time = event.timestamp
        if self.end_time is None or event.timestamp > self.end_time:
            self.end_time = event.timestamp

    @classmethod
    def from_events(cls, events: Iterable[AuditEvent]) -> EventSummary:
        summary = cls()
        for event in events:
            summary.add(event)
        return summary

    def render(self, *, invalid_rows: int) -> str:
        time_range = (
            f"{self.start_time.isoformat()} .. {self.end_time.isoformat()}"
            if self.start_time is not None and self.end_time is not None
            else "n/a"
        )
        status_codes = ", ".join(
            f"{'null' if code is None else code}: {count}"
            for code, count in sorted(
                self.status_codes.items(),
                key=lambda item: -1 if item[0] is None else item[0],
            )
        )
        return "\n".join(
            (
                f"events: {self.events}",
                f"actors: {len(self.actors)}",
                f"sources: {len(self.sources)}",
                f"time range: {time_range}",
                f"paths: {len(self.paths)}",
                f"status codes: {status_codes or 'n/a'}",
                f"invalid rows: {invalid_rows}",
            )
        )
