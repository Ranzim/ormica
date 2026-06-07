"""Tests for ormica.cortex.packs — composable Constitution packs."""
from __future__ import annotations

from pathlib import Path

import pytest

from ormica.cortex.loader import build_constitution
from ormica.cortex.packs import available_packs, load_pack


# --- bundled pack discovery + load -------------------------------------------


def test_available_packs_returns_bundled_yaml_stems():
    names = available_packs()
    # Sanity: at least the 4 starter packs we ship.
    for required in (
        "ftc-endorsement",
        "credential-leak-guard",
        "health-claims",
        "compact-output",
    ):
        assert required in names, f"{required} not in {names}"


@pytest.mark.parametrize("pack", available_packs())
def test_each_bundled_pack_loads_and_builds_into_constitution(pack: str):
    """Every shipped pack's rules must parse via build_constitution."""
    specs = load_pack(pack)
    assert isinstance(specs, list) and specs, f"{pack} has no rules"
    # If a rule factory name is wrong this raises — contract test catches
    # any pack that drifts out of sync with the rule registry.
    constitution = build_constitution(specs)
    assert len(list(constitution)) >= 1


# --- error paths --------------------------------------------------------------


def test_unknown_bundled_pack_errors_with_available_list():
    with pytest.raises(ValueError, match="unknown pack 'nope'"):
        load_pack("nope")


def test_missing_path_errors_with_path():
    with pytest.raises(ValueError, match="pack file not found"):
        load_pack("/tmp/does-not-exist.yaml")


def test_pack_with_non_list_rules_errors(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text("name: bad\nrules: not a list\n")
    with pytest.raises(ValueError, match="'rules' must be a list"):
        load_pack(str(p))


def test_pack_with_non_mapping_top_level_errors(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text("- just\n- a\n- list\n")
    with pytest.raises(ValueError, match="top level must be a mapping"):
        load_pack(str(p))


# --- custom-path packs --------------------------------------------------------


def test_user_supplied_path_loads(tmp_path: Path):
    """Teams shipping their own packs use a path; bundled name lookup is bypassed."""
    p = tmp_path / "mypack.yaml"
    p.write_text("""
name: custom
description: my company's house rules
rules:
  - max_tokens: 12345
""")
    specs = load_pack(str(p))
    assert specs == [{"max_tokens": 12345}]


# --- CLI / config integration -------------------------------------------------


def test_constitution_packs_via_yaml_config(tmp_path: Path):
    """`packs:` in ormica.yaml expands into a Constitution at _build_org time."""
    from ormica.cli.config import (
        BrainConfig,
        ConstitutionConfig,
        OrmicaConfig,
        save_config,
    )
    from ormica.cli.main import _build_org

    cfg_path = tmp_path / "ormica.yaml"
    save_config(
        OrmicaConfig(
            name="PackedCo",
            brain=BrainConfig(type="mock", replies=["ok"]),
            constitution=ConstitutionConfig(
                packs=["ftc-endorsement", "compact-output"],
                rules=[{"max_tokens": 50000}],
            ),
        ),
        cfg_path,
    )

    # Round-trip through load_config to mimic the real CLI path.
    from ormica.cli.config import load_config

    cfg = load_config(cfg_path)
    org = _build_org(cfg)

    # ftc-endorsement: 1 rule (banned_words). compact-output: 2.
    # inline: 1 (max_tokens). Total: 4.
    names = [r.name for r in org.constitution]
    assert len(names) == 4
    assert any(n.startswith("banned_words_") for n in names)
    assert "max_response_tokens_800" in names
    assert "min_response_length_20" in names
    assert "max_tokens_50000" in names


def test_unknown_pack_in_yaml_errors_clearly(tmp_path: Path):
    from ormica.cli.config import (
        BrainConfig,
        ConstitutionConfig,
        OrmicaConfig,
        save_config,
    )
    from ormica.cli.main import _build_org
    from ormica.cli.config import load_config

    cfg_path = tmp_path / "ormica.yaml"
    save_config(
        OrmicaConfig(
            name="X",
            brain=BrainConfig(type="mock", replies=["ok"]),
            constitution=ConstitutionConfig(packs=["typo-pack"]),
        ),
        cfg_path,
    )

    cfg = load_config(cfg_path)
    with pytest.raises(ValueError, match="unknown pack 'typo-pack'"):
        _build_org(cfg)
