"""Shared event ingestion contracts."""

from sentinelflow.core.errors import (
    EventValidationError,
    InputError,
    JsonlDecodeError,
)
from sentinelflow.core.jsonl import JsonlEventReader
from sentinelflow.core.models import AuditEvent, EventWindow
from sentinelflow.core.windowing import (
    WindowConfig,
    actor_source_path_key,
    iter_event_windows,
)

__all__ = [
    "AuditEvent",
    "EventValidationError",
    "EventWindow",
    "InputError",
    "JsonlDecodeError",
    "JsonlEventReader",
    "WindowConfig",
    "actor_source_path_key",
    "iter_event_windows",
]
