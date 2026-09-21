"""Ormica Forest — robustness by consensus (self-consistency).

One analyst is unreliable: it gets the answer right *most* of the time, but not
always. A **Forest** grows many independent colonies, lets each attempt the same
question, and takes the **majority vote** — so the wrong answers get outvoted.
No tree is authoritative; the right answer *emerges* from agreement across
independent attempts, the way running an LLM N times and taking the consensus
beats a single sample.

The demo is offline and deterministic (a `MockBrain` that is right ~`accuracy`
of the time, seeded for reproducibility). Watch individual trees disagree — and
the vote still land on the truth.

Run it::

    python examples/forest_vote/run.py
    python examples/forest_vote/run.py --trees 11 --accuracy 0.55
"""
from __future__ import annotations

import argparse
import random

from ormica import Forest, Ormica
from ormica.brain import MockBrain

QUESTION = "What is 6 * 7? Reply with only the number."
ANSWER = "42"
WRONG = ["41", "43", "48", "36", "44"]


def flaky_brain(accuracy: float) -> MockBrain:
    """One unreliable analyst: correct with probability ``accuracy``, else wrong.

    Each tree calls this brain once and draws independently, so the Forest sees
    a spread of answers — exactly the noise that voting is meant to smooth out.
    """

    def reply(messages) -> str:
        return ANSWER if random.random() < accuracy else random.choice(WRONG)

    return MockBrain(reply_fn=reply)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ormica forest voting demo")
    ap.add_argument("--trees", type=int, default=7, help="independent colonies")
    ap.add_argument("--accuracy", type=float, default=0.6, help="per-tree correctness")
    ap.add_argument("--seed", type=int, default=7, help="RNG seed (reproducible)")
    args = ap.parse_args(argv)
    random.seed(args.seed)

    forest = Forest(lambda: Ormica("tree"), size=args.trees)
    result = forest.solve(QUESTION, brain=flaky_brain(args.accuracy))

    print(f"question : {QUESTION}")
    print(f"trees    : {args.trees}  (each correct ~{args.accuracy:.0%} of the time)\n")
    print("individual answers: " + ", ".join(result.answers))
    print("\n" + result.pretty() + "\n")

    correct = result.answer == ANSWER
    wrong = sum(1 for a in result.answers if a != ANSWER)
    verdict = "✓ correct" if correct else "✗ wrong"
    print(f"consensus answer : {result.answer}   ({verdict}, {result.agreement:.0%} agreement)")
    print(
        f"{wrong}/{args.trees} individual trees were wrong — "
        f"the vote {'held' if correct else 'did not hold'}."
    )
    return 0 if correct else 1


if __name__ == "__main__":
    raise SystemExit(main())
