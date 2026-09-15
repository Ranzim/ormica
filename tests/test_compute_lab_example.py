"""Smoke test for the flagship example (examples/compute_lab/lab.py).

Runs it offline (deterministic mock) and proves the sandbox grounding actually
rejects a wrong answer — so the verify loop isn't vacuous.
"""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="the example runs code in the POSIX sandbox"
)

_LAB = Path(__file__).resolve().parents[1] / "examples" / "compute_lab" / "lab.py"


def _load():
    spec = importlib.util.spec_from_file_location("compute_lab_lab", _LAB)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_example_runs_offline_and_verifies_all():
    lab = _load()
    rc = lab.main([])  # no dashboard, offline mock
    assert rc == 0     # every problem verified by execution


def test_extract_code_strips_markdown_fences():
    lab = _load()
    assert lab.extract_code("```python\nprint(1)\n```") == "print(1)"
    assert lab.extract_code("print(2)") == "print(2)"


def test_grounding_accepts_correct_and_rejects_wrong():
    lab = _load()
    from ormica.sandbox import Sandbox

    rule = lab.grounded("42", Sandbox())
    ok = {"response": SimpleNamespace(content="print(6 * 7)")}
    bad = {"response": SimpleNamespace(content="print(6 * 8)")}
    assert rule.check(ok) is True     # runs, prints 42 → accepted
    assert rule.check(bad) is False   # runs, prints 48 → rejected (would trigger retry)
