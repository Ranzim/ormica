"""EventBus — pub/sub for observers."""
from __future__ import annotations

from time import time
from typing import Any

from .event import Event
from .observer import Observer


class EventBus:
    """Pub/sub for :class:`Observer` callbacks.

    One bad observer must never abort an emission — exceptions raised
    by ``notify`` are caught and dropped. Observers should keep their
    notify implementations cheap and side-effect-isolated.
    """

    def __init__(self) -> None:
        self._observers: list[Observer] = []

    def subscribe(self, observer: Observer) -> None:
        self._observers.append(observer)

    def unsubscribe(self, observer: Observer) -> None:
        try:
            self._observers.remove(observer)
        except ValueError:
            pass

    @property
    def observers(self) -> tuple[Observer, ...]:
        return tuple(self._observers)

    def emit(self, event_type: str, *, source: str = "", **payload: Any) -> Event:
        event = Event(
            type=event_type,
            timestamp=time(),
            source=source,
            payload=payload,
        )
        for obs in self._observers:
            try:
                obs.notify(event)
            except Exception:  # noqa: BLE001 — one bad observer can't kill the bus
                pass
        return event
