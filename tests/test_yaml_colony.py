"""Tests for the YAML colony loader."""
from pathlib import Path

import pytest

from ormica import Ormica
from ormica.colony import Colony, colonies, load_colony


def _write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


# --- load_colony --------------------------------------------------------------


def test_load_colony_returns_subclass(tmp_path: Path):
    yml = _write(
        tmp_path / "saas.yaml",
        """
name: saas_demo
description: B2B SaaS
templates:
  - name: product
    role: product
    task: Define and ship features
    system_prompt: Be a product PM
  - name: engineering
    role: engineering
""",
    )
    cls = load_colony(yml)
    assert issubclass(cls, Colony)
    assert cls.name == "saas_demo"
    assert cls.description == "B2B SaaS"


def test_loaded_colony_plants_templates(tmp_path: Path):
    yml = _write(
        tmp_path / "c.yaml",
        """
name: tiny
templates:
  - {name: a, role: scout}
  - {name: b, role: hunter}
""",
    )
    cls = load_colony(yml)
    org = Ormica("Acme")
    nodes = cls().plant(org)
    assert [n.name for n in nodes] == ["a", "b"]
    assert [n.role for n in nodes] == ["scout", "hunter"]


def test_load_with_register_true_makes_it_pluggable(tmp_path: Path):
    yml = _write(
        tmp_path / "regme.yaml",
        """
name: test_register_yaml
templates:
  - {name: alpha, role: alpha, system_prompt: Be quick}
""",
    )
    load_colony(yml, register=True)
    try:
        assert "test_register_yaml" in colonies()
        org = Ormica("X")
        nodes = org.plant("test_register_yaml")
        assert nodes[0].meta["system_prompt"] == "Be quick"
    finally:
        from ormica.colony.registry import _COLONIES

        _COLONIES.pop("test_register_yaml", None)


def test_missing_name_raises(tmp_path: Path):
    yml = _write(tmp_path / "broken.yaml", "templates: []\n")
    with pytest.raises(ValueError, match="missing required 'name'"):
        load_colony(yml)


def test_template_without_name_or_role_raises(tmp_path: Path):
    yml = _write(
        tmp_path / "broken.yaml",
        """
name: bad
templates:
  - {task: just a task}
""",
    )
    with pytest.raises(ValueError, match="needs at least 'name' or 'role'"):
        load_colony(yml)


def test_templates_not_a_list_raises(tmp_path: Path):
    yml = _write(tmp_path / "bad.yaml", "name: x\ntemplates: not a list\n")
    with pytest.raises(ValueError, match="must be a list"):
        load_colony(yml)


def test_empty_templates_section_allowed(tmp_path: Path):
    yml = _write(tmp_path / "empty.yaml", "name: vacant\n")
    cls = load_colony(yml)
    org = Ormica("X")
    assert cls().plant(org) == []


def test_template_rules_attach_to_planted_node(tmp_path: Path):
    """Per-template `rules:` in colony YAML drop onto the planted node's node.rules."""
    yml = _write(
        tmp_path / "with_rules.yaml",
        """
name: rule_demo
templates:
  - name: finance
    role: finance
    rules:
      - max_tokens: 10000
      - banned_words: [speculative]
""",
    )
    cls = load_colony(yml)
    org = Ormica("HQ")
    [finance] = cls().plant(org)
    # Two rules attached, each at the right stage.
    assert len(finance.rules) == 2
    stages = sorted(r.stage for r in finance.rules)
    assert stages == ["post", "pre"]


def test_template_rules_default_to_empty_tuple(tmp_path: Path):
    """Templates without a `rules:` field plant nodes with empty node.rules."""
    yml = _write(
        tmp_path / "no_rules.yaml",
        """
name: plain_demo
templates:
  - name: ops
    role: ops
""",
    )
    cls = load_colony(yml)
    org = Ormica("HQ")
    [ops] = cls().plant(org)
    assert ops.rules == []


def test_nested_children_plant_under_parent(tmp_path: Path):
    """`children:` blocks plant nested subtrees, returning every spawned node."""
    yml = _write(
        tmp_path / "nested.yaml",
        """
name: nested_demo
templates:
  - name: dept-a
    role: lead
    children:
      - name: team-1
        role: ic
        children:
          - name: ic-1
            role: ic-jr
      - name: team-2
        role: ic
""",
    )
    cls = load_colony(yml)
    org = Ormica("Acme", max_depth=10)
    nodes = cls().plant(org)
    # Pre-order: dept-a, team-1, ic-1, team-2
    assert [n.name for n in nodes] == ["dept-a", "team-1", "ic-1", "team-2"]
    assert [n.depth for n in nodes] == [1, 2, 3, 2]
    # And each child is actually under its parent in the tree
    team_1 = org.find("team-1")
    ic_1 = org.find("ic-1")
    assert ic_1.parent is team_1


def test_children_must_be_list(tmp_path: Path):
    yml = _write(
        tmp_path / "bad.yaml",
        """
name: bad
templates:
  - name: a
    role: a
    children: not a list
""",
    )
    with pytest.raises(ValueError, match="'children' must be a list"):
        load_colony(yml)


def test_nested_rules_attach_at_each_level(tmp_path: Path):
    """Per-node rules in nested templates land on the correct node."""
    yml = _write(
        tmp_path / "rules-nested.yaml",
        """
name: layered
templates:
  - name: top
    role: top
    rules:
      - max_response_tokens: 1500
    children:
      - name: mid
        role: mid
        rules:
          - banned_words: [secret]
""",
    )
    cls = load_colony(yml)
    org = Ormica("X")
    cls().plant(org)
    assert len(org.find("top").rules) == 1
    assert len(org.find("mid").rules) == 1
    assert org.find("mid").rules[0].name.startswith("banned_words_")


def test_template_rules_unknown_factory_errors_at_load_time(tmp_path: Path):
    """Typos in colony YAML rule names surface as ValueError when loading."""
    yml = _write(
        tmp_path / "bad_rules.yaml",
        """
name: typo_demo
templates:
  - name: ops
    role: ops
    rules:
      - not_a_real_rule: 1
""",
    )
    import pytest as _pytest  # local alias since this file doesn't import pytest at top
    with _pytest.raises(ValueError, match="not_a_real_rule"):
        load_colony(yml)


# --- CLI integration ----------------------------------------------------------


def test_cli_run_with_yaml_industry(tmp_path: Path, capsys):
    from ormica.cli.config import BrainConfig, OrmicaConfig, TaskConfig, save_config
    from ormica.cli.main import main

    industry_yaml = _write(
        tmp_path / "industry.yaml",
        """
name: cli_yaml_demo
templates:
  - {name: ops, role: ops}
  - {name: sales, role: sales}
""",
    )
    cfg_path = tmp_path / "ormica.yaml"
    save_config(
        OrmicaConfig(
            name="Acme",
            industry=str(industry_yaml),
            brain=BrainConfig(type="mock", replies=["done"]),
            tasks=[TaskConfig(description="hi", dept="sales")],
        ),
        cfg_path,
    )

    try:
        rc = main(["run", "--config", str(cfg_path)])
        assert rc == 0
        assert "succeeded=1" in capsys.readouterr().out
    finally:
        from ormica.colony.registry import _COLONIES

        _COLONIES.pop("cli_yaml_demo", None)
