"""Tests for the Preferences layer — objective-driven self-organization."""
import pytest

from ormica import Ormica, Preferences
from ormica.brain import MockBrain
from ormica.cortex import VerificationFailed, verifier


# --- the dials and derived knobs ----------------------------------------------


def test_presets_have_sensible_shape():
    q, c, f = Preferences.quality_first(), Preferences.cost_saver(), Preferences.fastest()
    # quality decomposes deeper and verifies harder than cost
    assert q.max_depth > c.max_depth
    assert q.verify_attempts > c.verify_attempts
    # speed parallelises more than cost
    assert f.concurrency > c.concurrency
    # cost keeps fan-out tight
    assert c.max_subtasks <= q.max_subtasks


def test_derived_knobs_are_bounded():
    for p in (Preferences.balanced(), Preferences.quality_first(),
              Preferences.cost_saver(), Preferences.fastest()):
        assert 1 <= p.max_depth <= 4
        assert 1 <= p.max_subtasks <= 6
        assert 1 <= p.verify_attempts <= 4
        assert 1 <= p.retries <= 5
        assert 1 <= p.concurrency <= 8


def test_custom_blend_and_validation():
    p = Preferences(cost=0.2, quality=0.9, speed=0.3)
    assert p.quality == 0.9
    assert "quality=0.9" in p.summary()
    with pytest.raises(ValueError, match="quality must be in"):
        Preferences(quality=1.5)


# --- wired into the colony ----------------------------------------------------


def test_colony_defaults_to_balanced():
    assert Ormica("Acme").preferences == Preferences.balanced()


def test_ask_verify_attempts_follow_preferences():
    # a verify rule that always fails → the agent retries exactly verify_attempts
    # times, and that count comes from Preferences.
    org = Ormica("Q", preferences=Preferences.quality_first())
    node = org.spawn("a")
    node.rules = [verifier("always_fail", lambda ctx: False, description="nope")]
    brain = MockBrain(reply_fn=lambda m: "x")
    with pytest.raises(VerificationFailed):
        org.ask("go", brain=brain, target="a")
    assert len(brain.calls) == org.preferences.verify_attempts == 4


def test_ask_explicit_override_beats_preferences():
    org = Ormica("Q", preferences=Preferences.quality_first())
    node = org.spawn("a")
    node.rules = [verifier("always_fail", lambda ctx: False, description="nope")]
    brain = MockBrain(reply_fn=lambda m: "x")
    with pytest.raises(VerificationFailed):
        org.ask("go", brain=brain, target="a", max_verify_attempts=2)
    assert len(brain.calls) == 2   # explicit wins over the preference


def test_solve_depth_and_fanout_come_from_preferences(monkeypatch):
    # capture what solve() hands to the DelegationBuilder
    import ormica.delegation as deleg
    captured = {}
    orig = deleg.DelegationBuilder.__init__

    def spy(self, org, node, brain, *, max_depth, max_subtasks, **kw):
        captured["max_depth"] = max_depth
        captured["max_subtasks"] = max_subtasks
        return orig(self, org, node, brain, max_depth=max_depth,
                    max_subtasks=max_subtasks, **kw)

    monkeypatch.setattr(deleg.DelegationBuilder, "__init__", spy)

    org = Ormica("Q", preferences=Preferences.quality_first())
    org.solve("do", brain=MockBrain(replies=["done"]))
    assert captured["max_depth"] == org.preferences.max_depth
    assert captured["max_subtasks"] == org.preferences.max_subtasks
