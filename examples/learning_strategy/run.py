"""Learn the whole strategy, not just the router.

The same stigmergic learning that finds the best *agent* finds the best **tool**
and the best **decomposition**, because a `StigmergicRouter` learns over any
`(kind, candidates)` pair. Point it at tool names or plan-template names and the
colony learns which strategy works for a kind of problem, from verified outcomes.

Offline and deterministic. Two learners run side by side:
  1. which TOOL solves an "extract" task best
  2. which DECOMPOSITION (plan shape) solves a "research" goal best

    python examples/learning_strategy/run.py
"""
from __future__ import annotations

import argparse
import random

from ormica import Ormica
from ormica.mycelium import Mycelium

# hidden "truth": each option's quality (correct-and-cheap score in 0..1). One is
# genuinely best in each set. The colony does not know this; it learns it.
TOOLS = {"regex": 0.90, "llm-parse": 0.20, "xpath": 0.15}
PLANS = {"map-reduce": 0.85, "single-shot": 0.20, "deep-tree": 0.45}


def _learn(org, kind, options, rounds, rng):
    # softer selection (higher temperature) keeps exploring, so every option is
    # sampled enough that the highest-quality one wins the trail. In real runs,
    # pheromone decay does the same job as time passes between tasks.
    router = org.stigmergic_router(temperature=1.0, explore=0.5)
    names = list(options)
    picks = []
    for _ in range(rounds):
        choice = router.select(kind, names, rng=rng)
        router.reinforce(kind, choice, options[choice])   # reward = that option's quality
        picks.append(choice)
    return router, names, picks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ormica learn-strategy demo")
    ap.add_argument("--rounds", type=int, default=80)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    rng = random.Random(args.seed)
    org = Ormica("Strategy Lab", memory=Mycelium(clock=lambda: 1000.0))
    win = max(5, args.rounds // 5)

    tr, tnames, tpicks = _learn(org, "extract", TOOLS, args.rounds, rng)
    print("\nLearning which TOOL to use for an 'extract' task:")
    for i in range(0, len(tpicks), win):
        w = tpicks[i:i + win]
        print(f"  rounds {i:>3}-{i + len(w) - 1:<3}  {'█' * round(w.count('regex') / len(w) * 22):<22} {w.count('regex') / len(w):.0%} → regex")
    print(f"  learned best tool: {tr.best('extract', tnames)}")

    pr, pnames, ppicks = _learn(org, "research", PLANS, args.rounds, rng)
    print("\nLearning which DECOMPOSITION to use for a 'research' goal:")
    for i in range(0, len(ppicks), win):
        w = ppicks[i:i + win]
        print(f"  rounds {i:>3}-{i + len(w) - 1:<3}  {'█' * round(w.count('map-reduce') / len(w) * 22):<22} {w.count('map-reduce') / len(w):.0%} → map-reduce")
    print(f"  learned best plan: {pr.best('research', pnames)}")

    print("\nSame mechanism, three decisions: agent, tool, and decomposition. The"
          "\ncolony learns its whole strategy from what actually verifies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
