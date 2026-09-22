"""Preferences — steer how the colony self-organizes toward an objective.

Emergence is powerful but, on its own, aimless: it grows *a* structure, not
necessarily the one you want. `Preferences` lets a user declare an **objective**
and have the colony bias its emergent behaviour accordingly — without touching
any agent code.

Three independent dials in ``[0, 1]``:

- **cost** — how much you want to spend as little as possible
- **quality** — how much you want the best possible answer
- **speed** — how much you want it fast

From those, the engine derives the knobs it actually consumes — how *deep* and
*wide* it decomposes a goal, how hard it *verifies/retries*, and how much it
*parallelises*. Quality buys depth + retries; cost trims them; speed widens
fan-out and concurrency.

    org = Ormica("Acme", preferences=Preferences.quality_first())
    org.solve(goal, brain=brain)   # deeper decomposition, more verify retries

    Ormica("Acme", preferences=Preferences.cost_saver())   # shallow + cheap
    Preferences(cost=0.2, quality=0.9, speed=0.3)           # or dial it yourself
"""
from __future__ import annotations

from dataclasses import dataclass


def _clamp(v: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(v))))


@dataclass(frozen=True)
class Preferences:
    """A user's objective, as three dials that bias emergent behaviour.

    The derived properties (:attr:`max_depth`, :attr:`max_subtasks`,
    :attr:`verify_attempts`, :attr:`retries`, :attr:`concurrency`) are what the
    engine reads. Presets cover the common cases; construct directly for a custom
    blend.
    """

    cost: float = 0.5
    quality: float = 0.5
    speed: float = 0.5

    def __post_init__(self) -> None:
        for name in ("cost", "quality", "speed"):
            v = getattr(self, name)
            if not (0.0 <= float(v) <= 1.0):
                raise ValueError(f"{name} must be in [0, 1], got {v!r}")

    # --- presets ---

    @classmethod
    def balanced(cls) -> "Preferences":
        return cls(cost=0.5, quality=0.5, speed=0.5)

    @classmethod
    def cost_saver(cls) -> "Preferences":
        return cls(cost=1.0, quality=0.3, speed=0.4)

    @classmethod
    def quality_first(cls) -> "Preferences":
        return cls(cost=0.2, quality=1.0, speed=0.3)

    @classmethod
    def fastest(cls) -> "Preferences":
        return cls(cost=0.5, quality=0.3, speed=1.0)

    # --- derived knobs the engine consumes ---

    @property
    def max_depth(self) -> int:
        """How deep to decompose (recursive delegation). Quality deepens; cost trims."""
        return _clamp(1 + 3 * self.quality - 1.5 * self.cost, 1, 4)

    @property
    def max_subtasks(self) -> int:
        """Fan-out per level. Quality *or* speed widens; cost narrows."""
        return _clamp(2 + 4 * max(self.quality, self.speed) - 2 * self.cost, 1, 6)

    @property
    def verify_attempts(self) -> int:
        """How many times to re-verify a wrong answer. Quality raises; speed lowers."""
        return _clamp(1 + 3 * self.quality - self.speed, 1, 4)

    @property
    def retries(self) -> int:
        """Transient-error retry budget (for wrapping a brain in RetryingBrain)."""
        return _clamp(1 + 4 * self.quality, 1, 5)

    @property
    def concurrency(self) -> int:
        """How many same-priority tasks to run at once. Speed raises."""
        return _clamp(1 + 7 * self.speed, 1, 8)

    def summary(self) -> str:
        return (
            f"cost={self.cost:.1f} quality={self.quality:.1f} speed={self.speed:.1f} "
            f"→ depth={self.max_depth} fanout={self.max_subtasks} "
            f"verify={self.verify_attempts} concurrency={self.concurrency}"
        )
