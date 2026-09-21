"""The Forest — many independent colonies, one answer by consensus.

A single colony (`Ormica`) grows one tree to solve a goal. A **Forest** grows
*many* — independent colonies that each attempt the same goal, with their
answers reconciled by **voting**, not by any one tree being authoritative. The
result is emergent at the population level: robustness comes from agreement
across independent attempts, the way an ensemble beats a single model
(self-consistency).

This stays on the emergence side of Ormica's philosophy — no fixed graph, no
coordinator picking a winner; the answer is whatever the population converges
on.

    forest = Forest(lambda: Ormica("tree"), size=5)
    result = forest.solve("What is 6 * 7?", brain=brain)
    result.answer       # the consensus answer
    result.agreement    # fraction of trees that agreed (0..1)
    result.consensus    # did agreement clear the threshold?

Each tree is a *fresh* colony (its own tree, memory, and signals), so attempts
are genuinely independent. Pair with grounding/verify inside each colony and the
Forest reconciles already-checked answers — two layers of reliability.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

__all__ = ["Forest", "ForestResult", "Vote", "majority_vote", "unanimous"]


@dataclass
class Vote:
    """One distinct answer and the trees that produced it."""

    answer: Any
    count: int
    voters: list[int] = field(default_factory=list)  # tree indices


@dataclass
class ForestResult:
    """The outcome of a Forest run: the consensus answer plus the full tally."""

    answer: Any                      # the plurality answer (None if no attempts)
    agreement: float                 # winning votes / total attempts (0..1)
    consensus: bool                  # did the winner clear the threshold (no tie)?
    votes: list[Vote]                # distinct answers, most-voted first
    answers: list                    # every raw per-tree answer, in tree order

    def pretty(self) -> str:
        lines = [
            f"consensus={self.consensus} agreement={self.agreement:.0%} "
            f"({len(self.answers)} trees)"
        ]
        for v in self.votes:
            lines.append(f"  {v.count:>2}x  {v.answer!r}")
        return "\n".join(lines)


def _key_str(value: Any) -> str:
    """A stable grouping key for a possibly-unhashable answer."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return f"{type(value).__name__}:{value}"
    try:
        return "json:" + json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return "repr:" + repr(value)


def majority_vote(
    answers: list,
    *,
    key: Optional[Callable[[Any], Any]] = None,
    threshold: float = 0.5,
) -> ForestResult:
    """Reconcile answers by plurality. Consensus requires a clear winner
    (no tie) whose share of the vote is at least ``threshold``.

    ``key`` maps an answer to what counts as "the same answer" — default is the
    value itself (great for numbers/strings; for typed artifacts pass
    ``key=lambda a: a.data``). The winning *raw* answer is still returned.
    """
    keyfn = key or (lambda a: a)
    groups: dict[str, dict] = {}
    for i, ans in enumerate(answers):
        k = _key_str(keyfn(ans))
        g = groups.setdefault(k, {"answer": ans, "voters": []})
        g["voters"].append(i)

    votes = [Vote(g["answer"], len(g["voters"]), g["voters"]) for g in groups.values()]
    votes.sort(key=lambda v: v.count, reverse=True)

    total = len(answers)
    top = votes[0] if votes else None
    agreement = (top.count / total) if (top and total) else 0.0
    no_tie = len(votes) == 1 or (len(votes) > 1 and votes[0].count > votes[1].count)
    consensus = bool(top) and no_tie and agreement >= threshold
    return ForestResult(
        answer=top.answer if top else None,
        agreement=agreement,
        consensus=consensus,
        votes=votes,
        answers=list(answers),
    )


def unanimous(answers: list, *, key: Optional[Callable[[Any], Any]] = None) -> ForestResult:
    """Consensus only if *every* tree produced the same answer."""
    return majority_vote(answers, key=key, threshold=1.0)


def _default_attempt(org: Any, goal: str, brain: Any) -> Any:
    """One tree's attempt: the root agent answers the goal directly."""
    from ormica.agent import Agent

    agent = Agent(
        org.root,
        brain,
        memory=org.memory,
        signals=org.signals,
        constitution=getattr(org, "constitution", None),
        budget=getattr(org, "budget", None),
    )
    agent.events = org.events
    return agent.act(goal).content


class Forest:
    """A population of independent colonies that vote on one goal.

    ``build`` is called once per tree to produce a *fresh* :class:`~ormica.Ormica`
    (independent tree/memory/signals). ``attempt(org, goal, brain) -> answer``
    runs one tree's attempt; the default has the root agent answer directly —
    supply your own to use ``org.solve`` (delegation), a task run, tools, etc.
    ``reconcile(answers) -> ForestResult`` turns the answers into a verdict
    (default: :func:`majority_vote`).
    """

    def __init__(
        self,
        build: Callable[[], Any],
        *,
        size: int = 5,
        attempt: Optional[Callable[[Any, str, Any], Any]] = None,
        reconcile: Callable[[list], ForestResult] = majority_vote,
    ) -> None:
        if size < 1:
            raise ValueError("a forest needs at least one tree")
        self.build = build
        self.size = size
        self.attempt = attempt or _default_attempt
        self.reconcile = reconcile

    def solve(self, goal: str, *, brain: Any) -> ForestResult:
        """Grow ``size`` fresh colonies, each attempts ``goal``, vote on the result."""
        answers = [self.attempt(self.build(), goal, brain) for _ in range(self.size)]
        return self.reconcile(answers)

    async def asolve(
        self, goal: str, *, brain: Any, concurrency: Optional[int] = None
    ) -> ForestResult:
        """Concurrent :meth:`solve` — attempts run in parallel (I/O-bound trees).

        Each attempt runs in a worker thread, so a plain sync ``attempt`` /
        ``brain`` parallelizes without needing an async brain. ``concurrency``
        caps how many run at once (default: all ``size``).
        """
        import asyncio

        sem = asyncio.Semaphore(concurrency or self.size)

        async def one() -> Any:
            async with sem:
                return await asyncio.to_thread(self.attempt, self.build(), goal, brain)

        answers = await asyncio.gather(*(one() for _ in range(self.size)))
        return self.reconcile(list(answers))
