"""MetricsObserver — always-on counters for monitoring a colony.

The Thought Trail lets you *read* what happened; metrics let you *monitor* it.
This observer tallies events as they fire and exposes a cheap snapshot: task
outcomes and failure rate, verify-retry rate, spawns and prunes, memory writes,
messages, and total tokens. It is subscribed by default, so ``org.metrics()``
always works.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .event import Event


class MetricsObserver:
    """Counts events and summarizes them. One Counter increment per event."""

    def __init__(self) -> None:
        self.counts: Counter = Counter()
        self.tokens: int = 0

    def notify(self, event: Event) -> None:
        self.counts[event.type] += 1
        if event.type == "think.recorded":
            self.tokens += int(event.payload.get("tokens_used", 0) or 0)

    def snapshot(self) -> dict:
        c = self.counts
        done = c.get("task.done", 0)
        failed = c.get("task.failed", 0) + c.get("task.dead", 0)
        total = done + failed

        def rate(x: float) -> float:
            return x / total if total else 0.0

        return {
            "tasks_done": done,
            "tasks_failed": failed,
            "failure_rate": round(rate(failed), 4),
            "verify_retries": c.get("verify.retry", 0),
            "verify_retry_rate": round(rate(c.get("verify.retry", 0)), 4),
            "spawns": c.get("node.spawned", 0),
            "prunes": c.get("node.pruned", 0),
            "memory_writes": c.get("memory.write", 0),
            "messages": c.get("message.sent", 0),
            "tokens": self.tokens,
            "events": dict(c),
        }


def cache_stats(brain: Any) -> dict:
    """Cache hit-rate for a brain wrapped in :class:`~ormica.brain.CachingBrain`."""
    hits = getattr(brain, "hits", None)
    misses = getattr(brain, "misses", None)
    if hits is None or misses is None:
        return {}
    total = hits + misses
    return {"cache_hits": hits, "cache_misses": misses,
            "cache_hit_rate": round(hits / total, 4) if total else 0.0}
