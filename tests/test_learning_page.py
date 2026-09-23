"""Tests for the dashboard learning view (templates.learning_page)."""
import random

from ormica import Ormica
from ormica.brain import MockBrain
from ormica.cortex import verifier
from ormica.dashboard.templates import learning_page
from ormica.mycelium import Mycelium


def test_empty_state_before_any_learning():
    html = learning_page(Ormica("X"))
    assert "No learning yet" in html
    assert "org.dispatch" in html


def test_shows_learned_specialist_after_dispatch():
    org = Ormica("X", memory=Mycelium(clock=lambda: 1000.0))
    for n in ("ace", "dud"):
        org.spawn(n, role="analyst")
    org.find("dud").rules = [verifier("no", lambda ctx: False, description="fails")]
    random.seed(0)
    for _ in range(30):
        org.dispatch("analyse", kind="analysis", candidates=["ace", "dud"],
                     brain=MockBrain(reply_fn=lambda m: "ok"))

    html = learning_page(org)
    assert "analysis" in html
    assert "specialist: ace" in html
