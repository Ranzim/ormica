"""Ormica Live Swarm — a busy colony to watch in the 3D graph.

This drives a colony through its *whole* life so every concept lights up in the
live `/graph` view at once:

  • **ants spawn** under nests (node.spawned) and **delegate** to sub-agent ants
  • **forage / think** — each act burns tokens, so the ant's **abdomen swells**
    with how much work it has done (the "task dimension")
  • **pheromone** written to shared memory (memory.write) and re-read (memory.read)
  • **harvests** brought home (think outputs)
  • **messages** recruit nestmates to a trail (message.sent)
  • **verify retries / failures** when an answer needs correcting
  • **pruning / decay** as spent branches die off (node.pruned)

Offline and deterministic-ish (a `MockBrain`, seeded) — no API key. It just
keeps the colony busy so there's always something moving.

Run it::

    python examples/live_swarm/run.py
    #   → open http://127.0.0.1:8777/graph
    python examples/live_swarm/run.py --agents 60 --pace 0.35
"""
from __future__ import annotations

import argparse
import random
import threading
import time

from ormica import Agent, Ormica
from ormica.brain import MockBrain
from ormica.cortex import verifier
from ormica.observe import MESSAGE_SENT

NESTS = ["Foraging", "Nursery", "Defense", "Scouting"]
ROLES = ["scout", "worker", "forager", "research", "analyst"]
TOPICS = ["food", "trail", "nest-site", "aphid-herd", "water", "threat", "sugar"]


def swarm_brain() -> MockBrain:
    """Replies of random length → variable tokens → variable abdomen size."""

    def reply(messages) -> str:
        return "harvest: " + "•" * random.randint(20, 420)

    return MockBrain(reply_fn=reply)


def _agent(org: Ormica, node, brain) -> Agent:
    a = Agent(node, brain, memory=org.memory, signals=org.signals)
    a.events = org.events           # wire the live event stream
    return a


def grow_branch(org: Ormica, brain, parent, depth: int, busy: list, cap: int) -> None:
    """Recursively split a task into sub-ants — but only *complex* subtasks branch
    further, so sibling branches reach uneven depths (task-driven), never a
    uniform fan-out. This is recursive delegation shaped by subtask complexity.
    """
    if depth <= 0 or len(list(org)) >= cap or getattr(parent, "depth", 0) >= 14:
        return
    for _ in range(random.randint(1, 3)):                     # subtask distribution
        if len(list(org)) >= cap:
            break
        try:
            child = org.spawn(
                f"{random.choice(ROLES)}-{random.randint(0, 99999)}",
                under=parent, role=random.choice(ROLES),
            )
        except Exception:      # depth cap / policy denial → this branch stops here
            break
        try:
            _agent(org, child, brain).act("subtask " + "•" * random.randint(20, 320))
        except Exception:
            pass
        if random.random() < 0.35:
            busy.append(child)
        # only a subtask that's "complex enough" recurses — and how deep varies
        if random.random() < 0.5:
            grow_branch(org, brain, child, depth - 1, busy, cap)


def tick(org: Ormica, brain, nests, busy, cap: int, t: int) -> None:
    """One beat of colony life — emits a spread of graph events."""
    pool = [n for n in org if n is not org.root and n.role != "dept"]
    size = len(list(org))

    # 1. grow: several new ants hatch under the nests each beat, until the cap.
    #    The colony keeps expanding — it doesn't sit at a fixed size.
    if size < cap:
        for _ in range(random.randint(2, 4)):
            nest = random.choice(nests)
            f = org.spawn(
                f"{random.choice(ROLES)}-{t}-{random.randint(0, 9999)}",
                under=nest, role=random.choice(ROLES),
            )
            if random.random() < 0.35:
                busy.append(f)

    # 2. forage: a few ants think (burn tokens → abdomen), lay & read pheromone
    for node in random.sample(pool, min(len(pool), random.randint(1, 3))) if pool else []:
        a = _agent(org, node, brain)
        try:
            a.act(f"forage {random.choice(TOPICS)}")             # think.recorded + harvest
        except Exception:
            pass
        if random.random() < 0.5:
            a.remember(f"{random.choice(TOPICS)}:{t}", "strong")  # memory.write (pheromone)
        if random.random() < 0.35:
            a.recall(f"{random.choice(TOPICS)}:{max(1, t - 3)}")  # memory.read

    # 3. keep a handful of ants working hard so their abdomens visibly balloon
    for node in [n for n in busy[-5:] if n in org]:
        try:
            _agent(org, node, brain).act("deep forage " + "•" * random.randint(80, 380))
        except Exception:
            pass

    # 4. recruit: one ant messages another to its trail (message.sent)
    if len(pool) >= 2 and random.random() < 0.45:
        s, r = random.sample(pool, 2)
        try:
            org.send(s, r, "recruit to trail")
        except Exception:
            pass
        org.events.emit(MESSAGE_SENT, source="swarm", sender=s.id, recipient=r.id)

    # 5. delegate: an ant splits its task into sub-ants; complex subtasks recurse
    #    deeper, so branches reach uneven depths. Deeper target depth = a harder
    #    task; most stay shallow, a few run deep (weighted).
    if pool and size < cap and random.random() < 0.6:
        parent = random.choice(pool)
        depth = random.choices([1, 2, 3, 4], weights=[3, 4, 2, 1])[0]  # task complexity
        grow_branch(org, brain, parent, depth, busy, cap)

    # 6. correct: occasionally an answer must be re-verified (verify.retry/failed)
    if pool and random.random() < 0.2:
        node = random.choice(pool)
        node.rules = [verifier("must_cite", lambda ctx: False, description="cite a source")]
        try:
            _agent(org, node, brain).act("summarise the trail", max_verify_attempts=2)
        except Exception:
            pass
        node.rules = []

    # 7. burn: once at cap, whole branches burn out — a chosen ant AND all its
    #    sub-ants and their children die together, so the fire cascades deeper the
    #    bigger/more-complex that branch grew (a shallow twig burns small, a deep
    #    sub-colony burns big). Prefer internal nodes so the burn really spreads.
    if size >= cap:
        branches = [n for n in org if n is not org.root and n.role != "dept"]
        withkids = [n for n in branches if n.children]
        pick = withkids or branches
        for _ in range(random.randint(1, 2)):
            if not pick:
                break
            victim = random.choice(pick)
            try:
                org.prune(victim)   # node.pruned → the graph sparks the whole subtree
            except Exception:
                pass
            pick = [n for n in pick if n in org]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ormica live swarm demo")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--agents", type=int, default=200, help="colony grows to this, then turns over")
    ap.add_argument("--pace", type=float, default=0.4, help="seconds between beats")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--ticks", type=int, default=0, help="stop after N beats (0 = forever)")
    ap.add_argument("--no-serve", action="store_true", help="run headless (no dashboard)")
    args = ap.parse_args(argv)
    random.seed(args.seed)

    org = Ormica("Ormica Live Swarm", max_depth=64)   # deep branches are the point
    brain = swarm_brain()
    nests = [org.spawn(name, role="dept") for name in NESTS]
    busy: list = []

    if not args.no_serve:
        from ormica.dashboard import serve

        threading.Thread(target=lambda: serve(org, port=args.port), daemon=True).start()
        time.sleep(1)
        print(f"🐜 live swarm → http://127.0.0.1:{args.port}/graph   (Ctrl+C to stop)\n")

    t = 0
    try:
        while args.ticks == 0 or t < args.ticks:
            t += 1
            tick(org, brain, nests, busy, args.agents, t)
            if not args.no_serve:
                time.sleep(args.pace)
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
