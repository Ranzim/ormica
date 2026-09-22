"""Ormica Learning Lab — a colony that discovers its own specialist.

Three analysts can take the same kind of task. Nobody is told who is good at it.
The colony routes each task with a stigmergic router, rewards the outcomes that
verified (correct) and were cheap, and lays pheromone accordingly. Watch it start
by exploring all three roughly equally, then converge on the one that actually
works. That convergence is the colony *learning*, with no training loop and no
labels beyond "did the answer pass verification".

Offline and deterministic (MockBrains, seeded) so you can run it with no key.

    python examples/learning/run.py
    python examples/learning/run.py --rounds 120
"""
from __future__ import annotations

import argparse
import random
from types import SimpleNamespace

from ormica import Ormica, route_reward
from ormica.brain import MockBrain
from ormica.cortex import Constitution, VerificationFailed, verifier

ANSWER = "42"
CANDIDATES = ["ace", "novice-1", "novice-2"]


def brain_for(name: str) -> MockBrain:
    """'ace' answers correctly and briefly; the novices ramble and get it wrong."""
    if name == "ace":
        return MockBrain(reply_fn=lambda m: ANSWER)
    return MockBrain(reply_fn=lambda m: "hmm, let me think... " + "well " * 40 + "7")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ormica stigmergic-learning demo")
    ap.add_argument("--rounds", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    rng = random.Random(args.seed)

    org = Ormica("Learning Lab")
    for name in CANDIDATES:
        org.spawn(name, role="analyst")
    # the answer only counts if it verifies as correct
    con = Constitution([verifier("correct", lambda ctx: ctx["response"].content.strip() == ANSWER)])
    router = org.stigmergic_router(temperature=0.4, explore=0.3)

    print(f"kind: 'estimate'   candidates: {', '.join(CANDIDATES)}\n")
    picks: list[str] = []
    for _ in range(args.rounds):
        node = router.select("estimate", CANDIDATES, rng=rng)
        agent = org.agent(node, brain=brain_for(node), constitution=con)
        try:
            resp = agent.act("Reply with the estimate.", max_verify_attempts=1)
            task = SimpleNamespace(status="done", tokens_used=resp.tokens_used)
        except VerificationFailed:
            task = SimpleNamespace(status="failed", tokens_used=0)
        router.reinforce("estimate", node, route_reward(task))
        picks.append(node)

    # learning curve: share of picks that went to the true specialist, per window
    win = max(5, args.rounds // 6)
    print("learning curve (share routed to the specialist 'ace' per window):")
    for i in range(0, len(picks), win):
        window = picks[i:i + win]
        share = window.count("ace") / len(window)
        bar = "█" * round(share * 24)
        print(f"  rounds {i:>3}-{i + len(window) - 1:<3}  {bar:<24} {share:.0%}")

    prefs = router.preferences("estimate", CANDIDATES)
    print("\nlearned preference (pheromone strength):")
    for c in sorted(prefs, key=lambda k: prefs[k], reverse=True):
        print(f"  {c:<10} {prefs[c]:.2f}")
    print(f"\nthe colony discovered its specialist: {router.best('estimate', CANDIDATES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
