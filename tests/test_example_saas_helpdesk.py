"""Smoke test for the SaaS helpdesk example.

Imports run.py's main() and executes it in a tmp cwd so the example
keeps working as the codebase evolves. Same shape as
test_example_emergent_swarm.py.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "saas_helpdesk"


@pytest.fixture
def example_in_tmp(tmp_path: Path) -> Path:
    """Copy the example into tmp_path so the test doesn't leave a db behind."""
    target = tmp_path / "saas_helpdesk"
    shutil.copytree(EXAMPLE_DIR, target)
    return target


def _load_run_module(example_dir: Path):
    spec = importlib.util.spec_from_file_location(
        "saas_helpdesk_run", example_dir / "run.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["saas_helpdesk_run"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_saas_helpdesk_run_succeeds(example_in_tmp: Path, monkeypatch, capsys):
    """`python run.py` completes with 0 failed tasks."""
    monkeypatch.chdir(example_in_tmp)
    module = _load_run_module(example_in_tmp)
    try:
        rc = module.main()
    finally:
        sys.modules.pop("saas_helpdesk_run", None)
    out = capsys.readouterr().out
    assert rc == 0
    assert "failed=0" in out
    # Live ticker output proves ConsoleObserver subscribed cleanly.
    assert "» task" in out
    assert "✓ task" in out
    # Trace persistence proves the TraceObserver wrote to mycelium.
    assert "persisted traces:" in out


def test_saas_helpdesk_tools_module_imports():
    """The tools module loads as plain Python (no Ormica boot required)."""
    name = "saas_helpdesk_tools"
    spec = importlib.util.spec_from_file_location(name, EXAMPLE_DIR / "tools.py")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass machinery can resolve cls.__module__.
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        # Sanity: lookup_customer is a @tool Tool and returns the expected shape.
        # Tool instances accept kwargs (matching the tool-call schema).
        result = module.lookup_customer(customer_id="acme-cust-001")
    finally:
        sys.modules.pop(name, None)
    assert "Acme Inc." in result
    assert "plan=Growth" in result
    assert "refund_eligible=no" in result


def test_saas_helpdesk_colony_yaml_loads(example_in_tmp: Path):
    """The colony YAML parses into a registered Colony with all 4 templates."""
    from ormica.colony import load_colony

    monkeypatch_dir = example_in_tmp
    colony_cls = load_colony(monkeypatch_dir / "colony.yaml")
    instance = colony_cls()
    templates = instance.templates()
    names = [t.name for t in templates]
    assert names == ["triage", "billing", "technical", "escalation"]
    # Each template carries the per-node rules declared in the YAML.
    rules_by_template = {t.name: t.rules for t in templates}
    assert len(rules_by_template["triage"]) == 2
    assert len(rules_by_template["billing"]) == 3
    assert len(rules_by_template["technical"]) == 2
    assert len(rules_by_template["escalation"]) == 2
