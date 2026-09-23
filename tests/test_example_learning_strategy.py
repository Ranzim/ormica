"""Smoke test for the learn-strategy demo (examples/learning_strategy/run.py)."""
import importlib.util
from pathlib import Path

_RUN = Path(__file__).resolve().parents[1] / "examples" / "learning_strategy" / "run.py"


def _load():
    spec = importlib.util.spec_from_file_location("learning_strategy_run", _RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_learns_best_tool_and_plan(capsys):
    run = _load()
    assert run.main(["--rounds", "120", "--seed", "0"]) == 0
    out = capsys.readouterr().out
    assert "learned best tool: regex" in out
    assert "learned best plan: map-reduce" in out
