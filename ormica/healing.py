"""Healing — how the colony recovers when work fails.

Three layers of resilience already exist below this one: `RetryingBrain`
(transient API errors), the verify stage (wrong answers), and durable `resume()`
(process crashes). `HealingPolicy` adds the *task and structure* layer:

- **retry with backoff** — a failed task is retried a few times before it's given up
- **dead-letter** — a task that exhausts its retries isn't silently lost; it's
  parked (``org.dead_letter``) and announced (`task.dead`) so you can inspect it
- **circuit breaker** — a target that keeps failing is taken out of rotation for
  a cooldown, so the colony stops hammering a broken branch
- **failure-driven re-organization** — when a target's circuit opens, the colony
  can **re-route** the work to the root, or **prune and respawn** the failing
  node — emergent self-repair, using the same primitives growth uses

Pass one to ``org.run(heal=…)``. Off by default (existing behaviour unchanged).

    org.run(brain=brain, heal=HealingPolicy.resilient())
    org.run(brain=brain, heal=HealingPolicy.from_preferences(org.preferences))
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HealingPolicy:
    """Declares how aggressively the colony repairs itself on failure."""

    max_retries: int = 2          # task-level retries *after* the first attempt
    backoff_base: float = 0.0     # seconds; delay = base * 2**(attempt-1), 0 = none
    backoff_max: float = 10.0
    circuit_threshold: int = 3    # consecutive failures on a target → open its circuit
    circuit_cooldown: float = 30.0  # seconds a circuit stays open
    reroute: bool = True          # while a target's circuit is open, route work to root
    respawn: bool = False         # when a circuit opens, prune + respawn that node

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.circuit_threshold < 1:
            raise ValueError("circuit_threshold must be >= 1")

    @classmethod
    def resilient(cls) -> "HealingPolicy":
        """A sensible production default: retry, break, reroute, and respawn."""
        return cls(max_retries=3, circuit_threshold=3, reroute=True, respawn=True)

    @classmethod
    def off(cls) -> "HealingPolicy":
        """No healing — one attempt per task (the bare-runner behaviour)."""
        return cls(max_retries=0, circuit_threshold=10**9, reroute=False, respawn=False)

    @classmethod
    def from_preferences(cls, prefs: object) -> "HealingPolicy":
        """Derive a policy from an objective: higher quality heals harder."""
        retries = int(getattr(prefs, "retries", 3))
        return cls(max_retries=max(0, retries - 1), circuit_threshold=3,
                   reroute=True, respawn=True)

    def backoff(self, attempt: int) -> float:
        return min(self.backoff_max, self.backoff_base * (2 ** max(0, attempt - 1)))
