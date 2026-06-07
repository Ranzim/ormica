"""Tests for the declarative rule loader (v0.2 step 4 — YAML Constitutions)."""
from __future__ import annotations

import pytest

from ormica.cortex import Constitution, Rule
from ormica.cortex.loader import RULE_FACTORIES, build_constitution, build_rule


# --- build_rule shape ---------------------------------------------------------


def test_bare_string_names_zero_arg_factory():
    """`"require_json"` → `require_json()`."""
    rule = build_rule("require_json")
    assert isinstance(rule, Rule)
    assert rule.stage == "post"
    assert rule.name == "require_json"


def test_single_key_dict_passes_int_arg():
    """`{"max_depth": 4}` → `max_depth(4)`."""
    rule = build_rule({"max_depth": 4})
    assert isinstance(rule, Rule)
    assert rule.stage == "spawn"
    assert rule.evaluate({"depth": 4}) is None
    assert rule.evaluate({"depth": 5}) is not None


def test_single_key_dict_passes_str_arg():
    """`{"block_role": "finance"}` → `block_role("finance")`."""
    rule = build_rule({"block_role": "finance"})
    assert rule.evaluate({"role": "finance"}) is not None
    assert rule.evaluate({"role": "ops"}) is None


def test_single_key_dict_passes_list_arg():
    """`{"banned_words": [...]}` → `banned_words([...])` (list is the single iterable arg)."""
    from dataclasses import dataclass

    @dataclass
    class _Resp:
        content: str

    rule = build_rule({"banned_words": ["secret", "internal"]})
    assert rule.evaluate({"response": _Resp("the secret")}) is not None
    assert rule.evaluate({"response": _Resp("public info")}) is None


def test_explicit_null_value_means_zero_arg():
    """`{"require_json": None}` → `require_json()`."""
    rule = build_rule({"require_json": None})
    assert rule.name == "require_json"


def test_unknown_rule_name_raises():
    with pytest.raises(ValueError) as exc_info:
        build_rule({"not_a_rule": 1})
    assert "not_a_rule" in str(exc_info.value)
    assert "Available" in str(exc_info.value)


def test_malformed_spec_raises():
    with pytest.raises(ValueError):
        build_rule(42)  # not str, not dict
    with pytest.raises(ValueError):
        build_rule({"a": 1, "b": 2})  # multi-key dict — ambiguous


def test_registry_covers_all_library_factories():
    """Sanity: every cortex.rules factory is reachable from YAML."""
    from ormica.cortex import rules

    factory_names = {
        name for name in vars(rules) if not name.startswith("_") and callable(vars(rules)[name])
    }
    factory_names -= {"Rule"}  # imported, not a factory
    # Pattern type alias is callable but not a factory.
    factory_names = {n for n in factory_names if n in {
        "max_depth", "block_role", "no_child_name", "unique_role_in_subtree",
        "max_tokens", "block_prompt_pattern", "min_task_description",
        "min_runtime_task_description",
        "banned_words", "banned_word_stems",
        "max_response_tokens", "min_response_length", "require_json",
    }}
    assert factory_names == set(RULE_FACTORIES)


# --- build_constitution -------------------------------------------------------


def test_build_constitution_mixed_specs():
    """A list of mixed string + dict specs builds a working Constitution."""
    constitution = build_constitution([
        {"max_depth": 4},
        {"max_tokens": 100_000},
        "require_json",
        {"banned_words": ["secret"]},
    ])
    assert isinstance(constitution, Constitution)
    assert len(constitution) == 4

    by_stage = {stage: constitution.for_stage(stage) for stage in ("spawn", "pre", "post")}
    assert len(by_stage["spawn"]) == 1
    assert len(by_stage["pre"]) == 1
    assert len(by_stage["post"]) == 2


# --- end-to-end: yaml.safe_load → Constitution -------------------------------


def test_yaml_round_trip_to_constitution():
    """The full path: YAML text → safe_load → build_constitution → enforce."""
    import yaml

    yaml_text = """
    rules:
      - max_depth: 4
      - max_tokens: 100000
      - block_role: finance
      - banned_words: [secret, confidential]
      - require_json
    """
    data = yaml.safe_load(yaml_text)
    constitution = build_constitution(data["rules"])
    assert len(constitution) == 5

    # Verify a representative rule actually fires correctly.
    spawn_rules = constitution.for_stage("spawn")
    assert any(r.evaluate({"role": "finance"}) is not None for r in spawn_rules)
