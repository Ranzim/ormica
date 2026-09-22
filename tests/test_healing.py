"""Tests for the self-healing layer — HealingPolicy in Ormica.run(heal=)."""
import pytest

from ormica import HealingPolicy, Ormica, Preferences
from ormica.brain import MockBrain


def _boom(_messages):
    raise RuntimeError("always fails")


# --- the policy ---------------------------------------------------------------


def test_policy_presets_and_validation():
    assert HealingPolicy.resilient().respawn is True
    assert HealingPolicy.off().max_retries == 0
    p = HealingPolicy.from_preferences(Preferences.quality_first())
    assert p.max_retries >= 1                    # quality heals harder
    assert HealingPolicy(max_retries=3, backoff_base=1).backoff(2) == 2.0
    with pytest.raises(ValueError):
        HealingPolicy(max_retries=-1)
    with pytest.raises(ValueError):
        HealingPolicy(circuit_threshold=0)


# --- retry with backoff -------------------------------------------------------


def test_task_retries_then_succeeds():
    calls = {}

    def flaky(messages):
        key = messages[-1].content
        calls[key] = calls.get(key, 0) + 1
        if calls[key] == 1:
            raise RuntimeError("transient")
        return "recovered"

    org = Ormica("Acme")
    org.spawn("w", role="w")
    org.task("do it", target="w")
    org.run(brain=MockBrain(reply_fn=flaky), heal=HealingPolicy(max_retries=2))

    t = org.tasks[0]
    assert t.status == "done" and t.result == "recovered"
    assert calls["do it"] == 2                   # failed once, retried, succeeded


def test_no_heal_means_single_attempt():
    org = Ormica("Acme")
    org.spawn("w")
    org.task("x", target="w")
    org.run(brain=MockBrain(reply_fn=_boom))     # no heal
    assert org.tasks[0].status == "failed"       # not retried, not dead


# --- dead-letter --------------------------------------------------------------


def test_exhausted_task_is_dead_lettered_and_announced():
    org = Ormica("Acme")
    org.spawn("w")
    org.task("x", target="w")
    seen = []
    org.subscribe(type("O", (), {"notify": lambda self, e: seen.append(e.type)})())

    org.run(brain=MockBrain(reply_fn=_boom),
            heal=HealingPolicy(max_retries=1, circuit_threshold=99))

    t = org.tasks[0]
    assert t.status == "dead"
    assert t in org.dead_letter
    assert "task.dead" in seen
    assert org.health()["dead"] == 1 and org.health()["dead_letter"] == 1


# --- circuit breaker + failure-driven re-org ----------------------------------


def test_open_circuit_reroutes_to_root():
    org = Ormica("Acme")
    org.spawn("bad")
    org.task("a", target="bad")
    org.task("b", target="bad")

    org.run(brain=MockBrain(reply_fn=_boom),
            heal=HealingPolicy(max_retries=0, circuit_threshold=1, reroute=True, respawn=False))

    # 'a' trips the circuit; 'b' is dequeued with the circuit open → rerouted to root
    a, b = org.tasks
    assert a.target == "bad"
    assert b.target == ""                        # healed by re-routing away from 'bad'


def test_open_circuit_respawns_the_failing_node():
    org = Ormica("Acme")
    original = org.spawn("bad", role="w").id
    org.task("a", target="bad")

    org.run(brain=MockBrain(reply_fn=_boom),
            heal=HealingPolicy(max_retries=0, circuit_threshold=1, respawn=True, reroute=False))

    revived = org.find("bad")                     # a fresh node stands in its place
    assert revived.id != original
    assert revived.role == "w"
