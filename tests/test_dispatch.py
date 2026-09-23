"""Tests for ambient learning via Ormica.dispatch()."""
import random

from ormica import Ormica
from ormica.brain import MockBrain
from ormica.cortex import verifier
from ormica.mycelium import Mycelium


def _org():
    # fixed clock so learning accumulates deterministically during the test
    org = Ormica("D", memory=Mycelium(clock=lambda: 1000.0))
    for name in ("ace", "dud1", "dud2"):
        org.spawn(name, role="analyst")
    # the duds fail verification, so only 'ace' produces a rewarded outcome
    fail = verifier("nope", lambda ctx: False, description="always fails")
    org.find("dud1").rules = [fail]
    org.find("dud2").rules = [fail]
    return org


def test_dispatch_routes_and_records_a_task():
    org = _org()
    t = org.dispatch("do it", kind="analysis", candidates=["ace", "dud1", "dud2"],
                     brain=MockBrain(reply_fn=lambda m: "answer"))
    assert t.target in {"ace", "dud1", "dud2"}
    assert t in org.tasks


def test_dispatch_learns_the_best_agent_over_calls():
    org = _org()
    random.seed(0)
    brain = MockBrain(reply_fn=lambda m: "answer")
    picks = []
    for _ in range(60):
        t = org.dispatch("analyse the data", kind="analysis",
                         candidates=["ace", "dud1", "dud2"], brain=brain)
        picks.append(t.target)

    # 'ace' is the only one whose output verifies, so the colony learns to route to it
    assert org.learner.best("analysis", ["ace", "dud1", "dud2"]) == "ace"
    assert picks[-15:].count("ace") >= 11          # converged on the specialist
    assert picks[:10].count("ace") < 30            # it explored first, did not hard-code
    prefs = org.learner.preferences("analysis", ["ace", "dud1", "dud2"])
    assert prefs["ace"] > prefs["dud1"] and prefs["ace"] > prefs["dud2"]


def test_learner_is_lazy_until_used():
    org = Ormica("D")
    assert org._learner is None
    _ = org.learner
    assert org._learner is not None
