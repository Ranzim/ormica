"""Smoke test for the forest-voting example (examples/forest_vote/run.py).

Runs it offline and deterministically (seeded) and proves the majority vote
lands on the correct answer despite some individual trees being wrong.
"""
import importlib.util
from pathlib import Path

_RUN = Path(__file__).resolve().parents[1] / "examples" / "forest_vote" / "run.py"


def _load():
    spec = importlib.util.spec_from_file_location("forest_vote_run", _RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_example_vote_holds_with_default_seed():
    run = _load()
    rc = run.main([])  # seeded → deterministic; consensus should be correct
    assert rc == 0


def test_example_reconciles_a_forest_result():
    run = _load()
    import random

    random.seed(7)
    forest = run.Forest(lambda: run.Ormica("tree"), size=7)
    result = forest.solve(run.QUESTION, brain=run.flaky_brain(0.6))
    assert result.answer == run.ANSWER
    assert result.consensus is True
    assert len(result.answers) == 7
    # some trees disagreed — the vote is doing real work
    assert any(a != run.ANSWER for a in result.answers)
