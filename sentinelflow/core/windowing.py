"""Deterministic bounded-memory time window construction."""

from __future__ import annotations

import hashlib
import heapq
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sentinelflow.core.models import AuditEvent, EventWindow

EntityKey = tuple[str, ...]
EntityKeyFunction = Callable[[AuditEvent], EntityKey]


@dataclass(frozen=True, slots=True)
class WindowConfig:
    """Configuration for fixed, possibly overlapping, half-open windows."""

    duration: timedelta
    overlap: timedelta = timedelta(0)

    def __post_init__(self) -> None:
        if self.duration <= timedelta(0):
            raise ValueError("window duration must be positive")
        if self.overlap < timedelta(0):
            raise ValueError("window overlap cannot be negative")
        if self.overlap >= self.duration:
            raise ValueError("window overlap must be shorter than duration")

    @property
    def step(self) -> timedelta:
        return self.duration - self.overlap


@dataclass(order=True, slots=True)
class _PendingWindow:
    end_time: datetime
    start_time: datetime
    entity_key: EntityKey
    events: list[AuditEvent] = field(default_factory=list, compare=False)


def actor_source_path_key(event: AuditEvent) -> EntityKey:
    """Return the default grouping key for parameter-enumeration analysis."""
    return (event.actor, event.source_ip, event.path)


def iter_event_windows(
    events: Iterable[AuditEvent],
    *,
    config: WindowConfig,
    key: EntityKeyFunction = actor_source_path_key,
) -> Iterator[EventWindow]:
    """Yield non-empty windows while retaining only currently open windows.

    Events must be globally ordered by timestamp. Windows are aligned to the Unix
    epoch and use ``start <= timestamp < end`` semantics.
    """
    active: dict[tuple[EntityKey, datetime], _PendingWindow] = {}
    close_order: list[_PendingWindow] = []
    previous: AuditEvent | None = None

    for event in events:
        if previous is not None and event.timestamp < previous.timestamp:
            raise ValueError(
                "events must be ordered by timestamp: "
                f"sequence {event.sequence_no} precedes sequence {previous.sequence_no}"
            )

        yield from _close_windows(
            close_order,
            active,
            before_or_at=event.timestamp,
        )

        entity_key = key(event)
        if not entity_key or any(not part for part in entity_key):
            raise ValueError("window entity key must contain non-empty strings")

        for start_time in _containing_starts(event.timestamp, config):
            active_key = (entity_key, start_time)
            pending = active.get(active_key)
            if pending is None:
                pending = _PendingWindow(
                    end_time=start_time + config.duration,
                    start_time=start_time,
                    entity_key=entity_key,
                )
                active[active_key] = pending
                heapq.heappush(close_order, pending)
            pending.events.append(event)
        previous = event

    yield from _close_windows(close_order, active, before_or_at=None)


def _containing_starts(timestamp: datetime, config: WindowConfig) -> Iterator[datetime]:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("event timestamps must include a timezone")

    timestamp_utc = timestamp.astimezone(UTC)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    step_us = _timedelta_microseconds(config.step)
    duration_us = _timedelta_microseconds(config.duration)
    elapsed_us = _timedelta_microseconds(timestamp_utc - epoch)
    latest_start_us = (elapsed_us // step_us) * step_us
    start_us = latest_start_us

    while elapsed_us < start_us + duration_us:
        yield epoch + timedelta(microseconds=start_us)
        start_us -= step_us


def _close_windows(
    close_order: list[_PendingWindow],
    active: dict[tuple[EntityKey, datetime], _PendingWindow],
    *,
    before_or_at: datetime | None,
) -> Iterator[EventWindow]:
    while close_order and (before_or_at is None or close_order[0].end_time <= before_or_at):
        pending = heapq.heappop(close_order)
        del active[(pending.entity_key, pending.start_time)]
        if pending.events:
            yield EventWindow(
                window_id=_window_id(
                    pending.entity_key,
                    pending.start_time,
                    pending.end_time,
                ),
                entity_key=pending.entity_key,
                start_time=pending.start_time,
                end_time=pending.end_time,
                events=tuple(pending.events),
            )


def _window_id(entity_key: EntityKey, start_time: datetime, end_time: datetime) -> str:
    material = "\x1f".join((*entity_key, start_time.isoformat(), end_time.isoformat())).encode()
    return f"window-{hashlib.sha256(material).hexdigest()[:16]}"


def _timedelta_microseconds(value: timedelta) -> int:
    return ((value.days * 86_400 + value.seconds) * 1_000_000) + value.microseconds
