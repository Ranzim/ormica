"""SSEObserver — fans events out to one queue per connected browser."""
from __future__ import annotations

import json
import queue
from typing import Any


class SSEObserver:
    """Observer that pushes each :class:`Event` to every subscribed queue.

    The dashboard's ``/events`` endpoint subscribes a fresh queue per
    HTTP connection, drains it inside the request handler, and writes
    each payload to the wire as a ``data: …\\n\\n`` frame. When the
    browser disconnects the handler unsubscribes the queue.

    Each queue has a bounded capacity — a slow consumer is dropped
    silently rather than blocking the runner. Default capacity 256
    events is generous for a UI; tune via ``capacity=``.
    """

    def __init__(self, *, capacity: int = 256) -> None:
        self.capacity = capacity
        self._queues: list[queue.Queue] = []

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=self.capacity)
        self._queues.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    def notify(self, event: Any) -> None:
        payload = json.dumps(
            {
                "type": event.type,
                "source": event.source,
                "payload": _jsonable(event.payload),
                "ts": event.timestamp,
            },
            default=str,
        )
        # Snapshot the subscriber list so a concurrent
        # subscribe/unsubscribe can't break iteration.
        for q in list(self._queues):
            try:
                q.put_nowait(payload)
            except queue.Full:
                # Drop on slow consumer rather than block the runner.
                pass


def _jsonable(value: Any) -> Any:
    """Best-effort make any payload JSON-encodable."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)
