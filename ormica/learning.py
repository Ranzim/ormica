"""Stigmergic learning — a colony that gets better the more it runs.

Pheromone signals already decay. This closes the other half of the loop, the one
that makes an ant colony *smart*: when a choice leads to a good outcome, lay down
**stronger** pheromone on it. Over many runs the colony converges on the choices
that work, and because trails still decay, it quietly forgets advice that stops
paying off. That is Ant Colony Optimization, applied to agent workflows.

The most useful decision to learn is **routing**: of several agents that could
take a task of some kind, which one actually produces verified, cheap answers?
No one assigns that. The colony discovers it.

    router = org.stigmergic_router()
    node = router.select("billing-question", candidates=["alice", "bob", "carol"])
    # ... run the task on `node`, then reward the outcome ...
    router.reinforce("billing-question", node, route_reward(task))

Give it a persistent backend and the learning survives restarts. Give it time and
it develops **emergent specialists**: the ant that keeps solving a kind of problem
keeps getting that kind of problem.
"""
from __future__ import annotations

import math
import random
from typing import Any, Optional


class StigmergicRouter:
    """Learns which candidate handles a *kind* of task best, from outcomes.

    Backed by a :class:`~ormica.stigma.Stigma` field. ``select`` samples a
    candidate weighted by its learned pheromone (with exploration so nothing is
    ruled out prematurely); ``reinforce`` rewards the choice that worked. Because
    the field decays, stale winners fade and the colony re-explores.
    """

    def __init__(
        self,
        signals: Any,
        *,
        temperature: float = 0.5,
        explore: float = 0.3,
        prefix: str = "route",
    ) -> None:
        if temperature <= 0:
            raise ValueError("temperature must be > 0")
        self.signals = signals
        self.temperature = temperature
        self.explore = explore     # baseline weight so untried options still get picked
        self.prefix = prefix

    def _key(self, kind: str, candidate: str) -> str:
        return f"{self.prefix}:{kind}:{candidate}"

    def preferences(self, kind: str, candidates: list[str]) -> dict[str, float]:
        """Current learned strength for each candidate (decay-adjusted)."""
        out: dict[str, float] = {}
        for c in candidates:
            sig = self.signals.sense(self._key(kind, c))
            out[c] = sig.strength if sig is not None else 0.0
        return out

    def select(self, kind: str, candidates: list[str], *, rng: Optional[random.Random] = None) -> str:
        """Pick a candidate, softmax-weighted by learned strength + exploration."""
        if not candidates:
            raise ValueError("need at least one candidate")
        r = rng or random
        strengths = self.preferences(kind, candidates)
        logits = [(strengths[c] + self.explore) / self.temperature for c in candidates]
        hi = max(logits)                                   # subtract max for numerical stability
        weights = [math.exp(x - hi) for x in logits]
        total = sum(weights)
        pick = r.random() * total
        acc = 0.0
        for c, w in zip(candidates, weights):
            acc += w
            if pick <= acc:
                return c
        return candidates[-1]

    def best(self, kind: str, candidates: list[str]) -> str:
        """The current front-runner (exploit only) — the learned specialist."""
        prefs = self.preferences(kind, candidates)
        return max(candidates, key=lambda c: prefs[c])

    def reinforce(self, kind: str, candidate: str, reward: float) -> None:
        """Lay pheromone on ``candidate`` for ``kind`` proportional to ``reward``.

        Reward <= 0 lays nothing, so a bad choice simply lets its trail decay.
        """
        if reward > 0:
            self.signals.reinforce(self._key(kind, candidate), amount=float(reward), by="router")


def route_reward(task: Any, *, scale: float = 500.0) -> float:
    """A reward in ``[0, 1]`` from a finished task: 0 if it didn't succeed,
    otherwise higher the *cheaper* it was (fewer tokens).

    Because a task that fails verification is marked ``failed`` (not ``done``),
    "done" already means "verified good" when a grounding rule is attached — so
    this rewards *correct and cheap*, exactly the ACO objective.
    """
    if getattr(task, "status", None) != "done":
        return 0.0
    tokens = getattr(task, "tokens_used", 0) or 0
    return 1.0 / (1.0 + tokens / scale)
