"""Smoke test for the architect example (examples/architect/run.py).

Runs it offline (deterministic MockBrain, no API key) and proves the colony
produces a schema-valid architecture artifact.
"""
import importlib.util
import json
from pathlib import Path

_RUN = Path(__file__).resolve().parents[1] / "examples" / "architect" / "run.py"


def _load():
    spec = importlib.util.spec_from_file_location("architect_run", _RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_design_returns_valid_architecture():
    run = _load()
    brain, label = run.pick_brain()          # no key in CI → MockBrain
    assert "MockBrain" in label
    spec = run.design("a ride-hailing platform", brain)
    # the result validates against the declared ArtifactType
    assert run.Architecture.problems(spec) == []
    assert spec["components"] and spec["connections"] and spec["data_stores"]


def test_main_runs_and_saves_spec(tmp_path):
    run = _load()
    out = tmp_path / "architecture.json"
    assert run.main([ "a chat app", "--out", str(out)]) == 0
    saved = json.loads(out.read_text())
    assert run.Architecture.problems(saved) == []
