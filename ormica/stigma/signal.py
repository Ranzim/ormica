"""A Signal — a single pheromone trail."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import time


@dataclass
class Signal:
    """A pheromone-style trail.

    ``strength`` is the stored intensity at ``last_touched`` (wall-clock seconds).
    Use :meth:`strength_at` to compute the decayed intensity at a later time;
    stigma never mutates stored signals to age them, decay is lazy.
    """

    topic: str
    strength: float
    sources: set[str] = field(default_factory=set)
    last_touched: float = field(default_factory=time)

    def strength_at(self, now: float, half_life: float) -> float:
        elapsed = now - self.last_touched
        if elapsed <= 0:
            return self.strength
        return self.strength * (0.5 ** (elapsed / half_life))
