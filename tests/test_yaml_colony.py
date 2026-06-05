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
