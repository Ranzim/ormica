"""Tests for stigmergic learning — the router that gets better from outcomes."""
import random
from types import SimpleNamespace

import pytest

from ormica import Ormica, StigmergicRouter, route_reward
from ormica.mycelium import Mycelium


def _org():
    # fixed clock → no decay during the test, so learning simply accumulates
    return Ormica("L", memory=Mycelium(clock=lambda: 1000.0))


CANDS = ["alice", "bob", "carol"]


# --- basics -------------------------------------------------------------------


def test_cold_start_explores_all_candidates():
    r = _org().stigmergic_router()
    rng = random.Random(0)
    picks = {r.select("k", CANDS, rng=rng) for _ in range(60)}
    assert picks == set(CANDS)        # with no pheromone, nothing is ruled out


def test_reinforce_shifts_preference():
    r = _org().stigmergic_router()
    assert r.preferences("k", CANDS) == {"alice": 0.0, "bob": 0.0, "carol": 0.0}
    r.reinforce("k", "bob", 1.0)
    prefs = r.preferences("k", CANDS)
    assert prefs["bob"] > 0 and prefs["alice"] == 0
    assert r.best("k", CANDS) == "bob"


def test_non_positive_reward_lays_no_trail():
    r = _org().stigmergic_router()
    r.reinforce("k", "alice", 0.0)
    r.reinforce("k", "bob", -1.0)
    assert r.preferences("k", CANDS) == {"alice": 0.0, "bob": 0.0, "carol": 0.0}


# --- the headline: it converges on the best candidate -------------------------


def test_router_learns_the_best_candidate():
    r = _org().stigmergic_router(temperature=0.4, explore=0.3)
    rng = random.Random(1)
    reward = {"alice": 1.0, "bob": 0.1, "carol": 0.1}   # alice is genuinely better

    picks = []
    for _ in range(300):
        choice = r.select("k", CANDS, rng=rng)
        r.reinforce("k", choice, reward[choice])
        picks.append(choice)

    # early on it explores; by the end it has learned to pick alice
    last = picks[-60:]
    assert last.count("alice") > 45          # strong convergence on the winner
    assert r.best("k", CANDS) == "alice"
    # …without ever hard-coding it: alice was discovered, not assigned
    assert picks[:10].count("alice") < 60


def test_learning_is_per_kind():
    r = _org().stigmergic_router()
    r.reinforce("billing", "alice", 5.0)
    r.reinforce("legal", "carol", 5.0)
    assert r.best("billing", CANDS) == "alice"
    assert r.best("legal", CANDS) == "carol"


# --- reward shaping: correct AND cheap ----------------------------------------


def test_route_reward_favours_cheap_success():
    cheap = route_reward(SimpleNamespace(status="done", tokens_used=10))
    dear = route_reward(SimpleNamespace(status="done", tokens_used=5000))
    failed = route_reward(SimpleNamespace(status="failed", tokens_used=10))
    assert 0.9 < cheap <= 1.0
    assert dear < cheap
    assert failed == 0.0


def test_router_rejects_bad_params():
    with pytest.raises(ValueError):
        StigmergicRouter(_org().signals, temperature=0)
    with pytest.raises(ValueError):
        StigmergicRouter(_org().signals, epsilon=1.0)


def test_epsilon_floor_prevents_hard_lock_in():
    # even after massively favoring one option, the others keep being sampled,
    # so the router can never permanently lock onto an early winner
    r = _org().stigmergic_router()               # defaults include epsilon + trail cap
    r.reinforce("k", "alice", 1000.0)
    rng = random.Random(0)
    picks = [r.select("k", CANDS, rng=rng) for _ in range(400)]
    assert picks.count("alice") > 300            # still mostly alice (it is best)
    assert picks.count("bob") >= 2 and picks.count("carol") >= 2   # but never starved
