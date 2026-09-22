"""Smoke test for the live-swarm demo (examples/live_swarm/run.py).

Runs the colony-life loop headless for a few beats and asserts the full spread
of graph events fires — so the demo that shows "everything working" really does.
"""
import collections
import importlib.util
from pathlib import Path

_RUN = Path(__file__).resolve().parents[1] / "examples" / "live_swarm" / "run.py"


def _load():
    spec = importlib.util.spec_from_file_location("live_swarm_run", _RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_swarm_emits_every_concept():
    run = _load()
    import random

    random.seed(7)
    org = run.Ormica("Test Swarm")
    counts: collections.Counter = collections.Counter()

    class _Obs:
        def notify(self, e):
            counts[e.type] += 1

    org.subscribe(_Obs())
    brain = run.swarm_brain()
    nests = [org.spawn(n, role="dept") for n in run.NESTS]
    busy: list = []
    for t in range(1, 61):
        run.tick(org, brain, nests, busy, 40, t)

    # every concept the graph visualises should have fired at least once
    for ev in (
        "node.spawned", "node.pruned", "memory.write", "memory.read",
        "message.sent", "think.recorded", "verify.retry", "verify.failed",
    ):
        assert counts[ev] > 0, f"expected {ev} events, got none"


def test_main_runs_headless():
    run = _load()
    assert run.main(["--no-serve", "--ticks", "10", "--seed", "3"]) == 0
