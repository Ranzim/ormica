"""Observers — receive events emitted by the colony."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import IO, Optional, Protocol, runtime_checkable

from .event import Event


@runtime_checkable
class Observer(Protocol):
    """Anything that can receive an :class:`Event`."""

    def notify(self, event: Event) -> None: ...


class LogObserver:
    """Prints one event per line. Default stream is ``stderr``.

    Output shape::

        2026-06-04T22:11:03Z task.done src=runner task_id=abc12345 target=sales
    """

    def __init__(self, stream: Optional[IO] = None) -> None:
        self.stream = stream if stream is not None else sys.stderr

    def notify(self, event: Event) -> None:
        ts = datetime.fromtimestamp(event.timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        parts = [ts, event.type]
        if event.source:
            parts.append(f"src={event.source}")
        for key, value in event.payload.items():
            parts.append(f"{key}={value}")
        print(" ".join(parts), file=self.stream)


class CounterObserver:
    """Counts events by type. Useful for assertions and lightweight metrics."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def notify(self, event: Event) -> None:
        self.counts[event.type] = self.counts.get(event.type, 0) + 1

    def get(self, event_type: str) -> int:
        return self.counts.get(event_type, 0)

    def total(self) -> int:
        return sum(self.counts.values())


class CollectObserver:
    """Stores every event in an in-memory list. Convenient for tests."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def notify(self, event: Event) -> None:
        self.events.append(event)

    def of_type(self, event_type: str) -> list[Event]:
        return [e for e in self.events if e.type == event_type]
