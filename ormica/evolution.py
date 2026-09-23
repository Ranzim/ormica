"""Evolutionary Forest — colonies that breed better strategies.

The Forest runs many colonies and votes. This goes one step further: treat each
colony's :class:`~ormica.Preferences` (its cost, quality, and speed dials) as a
**genome**, score how well it solved the goal, keep the best, and breed the next
generation by crossover and mutation. Over a few generations the population drifts
toward strategies that actually work, discovered rather than tuned by hand.

You supply an ``evaluate(prefs)`` that runs a colony with those preferences and
returns ``(answer, fitness)``. Fitness is anything you can measure: did it verify,
how good was it, how cheap. Everything else is a standard evolutionary loop.

    result = evolve(my_evaluate, generations=4, population=6, seed=0)
    result.best.prefs        # the preferences that won
    result.best.answer       # what that colony produced
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .preferences import Preferences


@dataclass
class Genome:
    """One candidate strategy: its preferences, its score, and what it produced."""

    prefs: Preferences
    fitness: float = 0.0
    answer: Any = None


@dataclass
class EvolutionResult:
    best: Genome
    history: list[list[Genome]] = field(default_factory=list)  # each generation, sorted

    def pretty(self) -> str:
        lines = []
        for g, gen in enumerate(self.history):
            top = gen[0]
            lines.append(f"gen {g}: best fitness {top.fitness:.3f}  ({top.prefs.summary()})")
        lines.append(f"winner: fitness {self.best.fitness:.3f}  ({self.best.prefs.summary()})")
        return "\n".join(lines)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _mutate(p: Preferences, sigma: float, rng: random.Random) -> Preferences:
    return Preferences(
        cost=_clamp01(p.cost + rng.gauss(0, sigma)),
        quality=_clamp01(p.quality + rng.gauss(0, sigma)),
        speed=_clamp01(p.speed + rng.gauss(0, sigma)),
    )


def _crossover(a: Preferences, b: Preferences, rng: random.Random) -> Preferences:
    pick = lambda x, y: x if rng.random() < 0.5 else y  # noqa: E731
    return Preferences(
        cost=pick(a.cost, b.cost),
        quality=pick(a.quality, b.quality),
        speed=pick(a.speed, b.speed),
    )


def evolve(
    evaluate: Callable[[Preferences], "tuple[Any, float]"],
    *,
    generations: int = 4,
    population: int = 6,
    survivors: int = 2,
    mutation: float = 0.15,
    seed: Optional[int] = None,
    base: Optional[list[Preferences]] = None,
) -> EvolutionResult:
    """Evolve ``Preferences`` toward higher fitness.

    ``evaluate(prefs) -> (answer, fitness)`` runs a colony with those preferences
    and scores it. Each generation keeps the top ``survivors`` and refills the
    rest by crossing two survivors and mutating. Returns the best genome seen and
    the full per-generation history.
    """
    if population < 2 or survivors < 1 or survivors >= population:
        raise ValueError("need population >= 2 and 1 <= survivors < population")
    rng = random.Random(seed)

    pool: list[Preferences] = list(base or [])
    while len(pool) < population:
        pool.append(Preferences(cost=rng.random(), quality=rng.random(), speed=rng.random()))
    pool = pool[:population]

    best: Optional[Genome] = None
    history: list[list[Genome]] = []

    for _ in range(generations):
        graded = []
        for prefs in pool:
            answer, fitness = evaluate(prefs)
            graded.append(Genome(prefs=prefs, fitness=float(fitness), answer=answer))
        graded.sort(key=lambda g: g.fitness, reverse=True)
        history.append(graded)
        if best is None or graded[0].fitness > best.fitness:
            best = graded[0]

        elite = [g.prefs for g in graded[:survivors]]
        nxt = list(elite)                                    # survivors carry over
        while len(nxt) < population:
            a, b = rng.choice(elite), rng.choice(elite)
            nxt.append(_mutate(_crossover(a, b, rng), mutation, rng))
        pool = nxt

    assert best is not None
    return EvolutionResult(best=best, history=history)
