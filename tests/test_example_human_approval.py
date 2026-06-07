"""Smoke test for examples/human_approval.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "human_approval.py"


def test_human_approval_demo_runs(capsys):
    """The non-interactive demos succeed end-to-end."""
    name = "human_approval_demo"
    spec = importlib.util.spec_from_file_location(name, EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        rc = module.main()
    finally:
        sys.modules.pop(name, None)

    assert rc == 0
    out = capsys.readouterr().out
    # Scripted stdin ConsoleApprover demo ran.
    assert "finance approved via scripted 'y' input" in out
    # CallbackApprover demo ran and made both decisions.
    assert "finance: approved by callback" in out
    assert "legal: denied by callback" in out
