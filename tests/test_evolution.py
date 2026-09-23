"""Tests for the Evolutionary Forest — breeding better strategies."""
import pytest

from ormica import Preferences, evolve
from ormica.evolution import _crossover, _mutate


def test_evolves_toward_higher_fitness():
    # a synthetic world where quality is what matters; evolution should discover it
    def evaluate(prefs):
        return f"answer@q={prefs.quality:.2f}", prefs.quality

    result = evolve(evaluate, generations=6, population=8, survivors=2, seed=0)

    assert result.best.prefs.quality > 0.85          # found the high-quality region
    first_gen_best = result.history[0][0].fitness
    last_gen_best = result.history[-1][0].fitness
    assert last_gen_best >= first_gen_best            # never regresses
    assert len(result.history) == 6


def test_best_answer_is_carried():
    def evaluate(prefs):
        return {"used": prefs.cost}, prefs.cost      # reward cost dial here

    result = evolve(evaluate, generations=4, population=6, seed=1)
    assert result.best.prefs.cost > 0.8
    assert result.best.answer == {"used": result.best.prefs.cost}


def test_can_seed_the_starting_population():
    seed_prefs = [Preferences.quality_first(), Preferences.cost_saver()]
    calls = []

    def evaluate(prefs):
        calls.append(prefs)
        return None, prefs.quality

    evolve(evaluate, generations=1, population=4, seed=0, base=seed_prefs)
    # the provided genomes were evaluated in gen 0
    assert any(p.quality == 1.0 for p in calls[:4])
    assert any(p.cost == 1.0 for p in calls[:4])


def test_genetic_ops_stay_in_range():
    import random

    rng = random.Random(0)
    child = _mutate(Preferences(0.5, 0.5, 0.5), 0.5, rng)
    for v in (child.cost, child.quality, child.speed):
        assert 0.0 <= v <= 1.0
    x = _crossover(Preferences.cost_saver(), Preferences.fastest(), rng)
    assert 0.0 <= x.quality <= 1.0


def test_rejects_bad_config():
    with pytest.raises(ValueError):
        evolve(lambda p: (None, 0.0), population=1)
    with pytest.raises(ValueError):
        evolve(lambda p: (None, 0.0), population=4, survivors=4)
