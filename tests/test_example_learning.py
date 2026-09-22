"""Smoke test for the learning demo (examples/learning/run.py).

Runs it offline and deterministically and proves the colony converges on the
real specialist.
"""
import importlib.util
from pathlib import Path

_RUN = Path(__file__).resolve().parents[1] / "examples" / "learning" / "run.py"


def _load():
    spec = importlib.util.spec_from_file_location("learning_run", _RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_demo_converges_on_the_specialist(capsys):
    run = _load()
    rc = run.main(["--rounds", "40", "--seed", "0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "discovered its specialist: ace" in out
