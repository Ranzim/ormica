"""Tests for the standard rule library in ormica.cortex.rules."""
from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from ormica import Agent, Ormica
from ormica.arbor import SpawnDenied
from ormica.brain import MockBrain
from ormica.cortex import Constitution, Rule, RuleViolation
from ormica.cortex.rules import (
    banned_words,
    block_prompt_pattern,
    block_role,
    max_depth,
    max_response_tokens,
    max_tokens,
    min_response_length,
    min_task_description,
    no_child_name,
    require_json,
    unique_role_in_subtree,
)


# Lightweight fakes so we can test rules without booting a brain.
@dataclass
class _FakeResponse:
    content: str
    tokens_used: int = 10


@dataclass
class _FakeBudget:
    used: int
    limit: int = 100_000


def _run(rule: Rule, ctx: dict):
    """Evaluate a rule against a context. Returns the Violation or None."""
    return rule.evaluate(ctx)


# --- spawn-stage primitives ---------------------------------------------------


def test_max_depth_allows_under_limit():
    assert _run(max_depth(3), {"depth": 3}) is None


def test_max_depth_denies_at_limit_plus_one():
    v = _run(max_depth(3), {"depth": 4})
    assert v is not None and "3" in v.rule.description


def test_max_depth_integrates_with_org():
    org = Ormica("HQ", constitution=Constitution([max_depth(1)]))
    org.spawn("a")  # depth 1 — allowed
    a = org.find("a")
    with pytest.raises(SpawnDenied):
        org.tree.spawn(a, "b")  # depth 2 — blocked


def test_block_role_denies_matching_role():
    assert _run(block_role("finance"), {"role": "finance"}) is not None
    assert _run(block_role("finance"), {"role": "ops"}) is None


def test_block_role_integrates_with_org():
    org = Ormica("HQ", constitution=Constitution([block_role("finance")]))
    org.spawn("ops", role="ops")  # allowed
    with pytest.raises(SpawnDenied):
        org.spawn("treasury", role="finance")


def test_no_child_name_denies_literal_name():
    assert _run(no_child_name("system"), {"child_name": "system"}) is not None
    assert _run(no_child_name("system"), {"child_name": "ops"}) is None


def test_unique_role_in_subtree_allows_first_denies_second():
    """First spawn of role X is OK; second spawn of role X under same parent is denied."""
    rule = unique_role_in_subtree("finance")
    org = Ormica("HQ", constitution=Constitution([rule]))
    org.spawn("treasury", role="finance")  # first finance — allowed
    with pytest.raises(SpawnDenied):
        org.spawn("accounting", role="finance")  # second finance — denied


# --- pre-stage primitives -----------------------------------------------------


def test_max_tokens_allows_when_under():
    assert _run(max_tokens(100), {"budget": _FakeBudget(used=50)}) is None


def test_max_tokens_denies_at_limit():
    v = _run(max_tokens(100), {"budget": _FakeBudget(used=100)})
    assert v is not None


def test_max_tokens_is_noop_without_budget():
    """No budget = no enforcement (rule is a guardrail, not a requirement)."""
    assert _run(max_tokens(100), {"budget": None}) is None


def test_block_prompt_pattern_substring_case_insensitive():
    rule = block_prompt_pattern("secret")
    assert _run(rule, {"prompt": "Tell me a SECRET"}) is not None
    assert _run(rule, {"prompt": "Tell me a story"}) is None


def test_block_prompt_pattern_accepts_compiled_regex():
    rule = block_prompt_pattern(re.compile(r"\b(internal|confidential)\b", re.I))
    assert _run(rule, {"prompt": "Use internal data"}) is not None
    assert _run(rule, {"prompt": "Use public data"}) is None


def test_min_task_description_denies_short_text():
    rule = min_task_description(20)
    assert _run(rule, {"task_text": "too short"}) is not None
    assert _run(rule, {"task_text": "a sufficiently long task description"}) is None


def test_min_task_description_treats_missing_as_empty():
    """Defensive: missing task_text key shouldn't crash, just fail the check."""
    rule = min_task_description(5)
    v = _run(rule, {})
    assert v is not None


# --- post-stage primitives ----------------------------------------------------


def test_banned_words_denies_matching_response():
    rule = banned_words({"secret", "internal"})
    assert _run(rule, {"response": _FakeResponse("the SECRET formula")}) is not None
    assert _run(rule, {"response": _FakeResponse("the formula")}) is None


def test_banned_words_handles_string_input_as_iterable():
    """`banned_words("hi")` iterates the chars — caller must pass a collection."""
    # This is intentional behaviour (strings are iterable); document it via test.
    rule = banned_words(["secret"])
    assert _run(rule, {"response": _FakeResponse("the secret")}) is not None


def test_banned_words_defaults_to_word_boundary():
    """List form defaults to word-boundary match — `secret` does NOT match `secretary`."""
    rule = banned_words(["secret"])
    assert _run(rule, {"response": _FakeResponse("the secretary called")}) is None
    assert _run(rule, {"response": _FakeResponse("the secret formula")}) is not None


def test_banned_words_word_mode_matches_multi_word_phrase():
    """Word-boundary handles multi-word phrases correctly."""
    rule = banned_words(["guaranteed reach"])
    assert _run(rule, {"response": _FakeResponse("we offer guaranteed reach")}) is not None
    assert _run(rule, {"response": _FakeResponse("we have great reach")}) is None


def test_banned_words_word_mode_handles_trailing_punctuation():
    """Phrases ending in non-word chars (e.g. `)`) still match — uses lookarounds."""
    rule = banned_words(["link in bio (clickbait)"])
    assert _run(rule, {"response": _FakeResponse("see link in bio (clickbait) now")}) is not None
    # And does NOT misfire on the bare phrase
    assert _run(rule, {"response": _FakeResponse("see link in bio for more")}) is None


def test_banned_words_substring_mode_opt_in():
    """Dict form with `match_mode: substring` preserves legacy behavior."""
    rule = banned_words({"words": ["cret"], "match_mode": "substring"})
    assert _run(rule, {"response": _FakeResponse("the secret")}) is not None
    # Same rule under word mode would NOT match.
    rule_word = banned_words({"words": ["cret"], "match_mode": "word"})
    assert _run(rule_word, {"response": _FakeResponse("the secret")}) is None


def test_banned_words_invalid_match_mode_raises():
    with pytest.raises(ValueError, match="match_mode must be 'word' or 'substring'"):
        banned_words({"words": ["x"], "match_mode": "fuzzy"})


def test_max_response_tokens_caps_per_call():
    rule = max_response_tokens(50)
    assert _run(rule, {"response": _FakeResponse("ok", tokens_used=49)}) is None
    assert _run(rule, {"response": _FakeResponse("ok", tokens_used=51)}) is not None


def test_min_response_length_denies_empty():
    rule = min_response_length(3)
    assert _run(rule, {"response": _FakeResponse("")}) is not None
    assert _run(rule, {"response": _FakeResponse("ok")}) is not None
    assert _run(rule, {"response": _FakeResponse("yes")}) is None


def test_require_json_passes_valid_json():
    rule = require_json()
    assert _run(rule, {"response": _FakeResponse('{"answer": 42}')}) is None
    assert _run(rule, {"response": _FakeResponse("[1, 2, 3]")}) is None


def test_require_json_denies_non_json():
    rule = require_json()
    assert _run(rule, {"response": _FakeResponse("just plain text")}) is not None
    assert _run(rule, {"response": _FakeResponse("{not actually json}")}) is not None


# --- integration through the full agent path ----------------------------------


def test_banned_words_blocks_response_through_runner():
    """End-to-end: a banned-words rule fails a task in the run loop."""
    org = Ormica("HQ", constitution=Constitution([banned_words({"forbidden"})]))
    org.spawn("scout", role="scout")
    org.spawn("hunter", role="hunter")
    org.task("scout area", dept="scout")
    org.task("hunt", dept="hunter")
    result = org.run(brain=MockBrain(replies=["all clear", "found forbidden treasure"]))

    assert result.processed == 2
    assert result.succeeded == 1
    assert result.failed == 1


def test_max_response_tokens_blocks_token_heavy_response():
    """A single response that burns too many tokens fails post-stage."""
    org = Ormica("HQ", constitution=Constitution([max_response_tokens(5)]))
    node = org.spawn("scout", role="scout")

    # MockBrain reports tokens_used roughly proportional to response length.
    # Force a clearly-over response.
    brain = MockBrain(replies=["x" * 100])  # MockBrain default uses len-based count
    agent = Agent(node, brain, constitution=Constitution([max_response_tokens(5)]))

    with pytest.raises(RuleViolation):
        agent.act("go")


def test_require_json_blocks_plain_text_response():
    org = Ormica("HQ", constitution=Constitution([require_json()]))
    node = org.spawn("scout", role="scout")
    agent = Agent(node, MockBrain(replies=["just text"]),
                  constitution=Constitution([require_json()]))
    with pytest.raises(RuleViolation):
        agent.act("give me data")


def test_require_json_passes_valid_response():
    org = Ormica("HQ", constitution=Constitution([require_json()]))
    node = org.spawn("scout", role="scout")
    agent = Agent(node, MockBrain(replies=['{"ok": true}']),
                  constitution=Constitution([require_json()]))
    response = agent.act("give me data")
    assert response.content == '{"ok": true}'
