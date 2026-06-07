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


class ConsoleObserver:
    """Human-readable live ticker for ``ormica run``.

    Subscribes to lifecycle and constitution events and prints a single
    line per occurrence with a leading symbol so a user watching the
    terminal can follow the colony's progress in real time::

        » task abc12345 started  (target=sales priority=high)
          look north
        ✓ task abc12345 done     (tokens=42)
        ✗ task def67890 failed   RuleViolation: ban_secret: …
        ⚠ rule.soft fired        rule=prefer_short stage=post node=scout

    Pass ``include_run=True`` to also print run start/complete summaries.
    Default stream is stdout; pass another file-like to redirect.
    """

    def __init__(
        self,
        stream: Optional[IO] = None,
        *,
        include_run: bool = False,
    ) -> None:
        self.stream = stream if stream is not None else sys.stdout
        self.include_run = include_run

    def notify(self, event: Event) -> None:
        from .event import (
            RULE_SOFT_VIOLATION,
            RUN_COMPLETED,
            RUN_STARTED,
            TASK_DONE,
            TASK_FAILED,
            TASK_STARTED,
        )

        et = event.type
        p = event.payload
        if et == TASK_STARTED:
            target = p.get("target") or "root"
            line = f"» task {p.get('task_id', '?')[:8]} started  (target={target} priority={p.get('priority', '?')})"
            print(line, file=self.stream)
            desc = p.get("description") or ""
            if desc:
                print(f"  {desc}", file=self.stream)
        elif et == TASK_DONE:
            tokens = p.get("tokens_used", 0)
            print(
                f"✓ task {p.get('task_id', '?')[:8]} done     (tokens={tokens})",
                file=self.stream,
            )
        elif et == TASK_FAILED:
            err = p.get("error") or "(no error message)"
            print(
                f"✗ task {p.get('task_id', '?')[:8]} failed   {err}",
                file=self.stream,
            )
        elif et == RULE_SOFT_VIOLATION:
            print(
                f"⚠ rule.soft fired  rule={p.get('rule')} "
                f"stage={p.get('stage')} node={p.get('node')}",
                file=self.stream,
            )
        elif self.include_run and et == RUN_STARTED:
            print(
                f"▶ run started  ({p.get('n_tasks', 0)} task(s), mode={p.get('mode')})",
                file=self.stream,
            )
        elif self.include_run and et == RUN_COMPLETED:
            print(
                f"■ run complete  processed={p.get('processed', 0)} "
                f"succeeded={p.get('succeeded', 0)} failed={p.get('failed', 0)}",
                file=self.stream,
            )
