"""Tests for the two onboarding-pitfall rule factories added in v0.3.

Background: the live influencer demo surfaced two surprises that bit a
first-time user equally regardless of vertical:

  1. ``min_task_description`` reads the SPAWN-time Node.task string,
     not the runtime task description — confusing because the name
     strongly implies the runtime ask. v0.3 ships the sibling
     ``min_runtime_task_description`` that does what the name implies.

  2. ``banned_words`` does case-insensitive *substring* match, so
     ``"guaranteed"`` does NOT catch ``"guaranteeing"``. v0.3 ships
     ``banned_word_stems`` with regex word-boundary + suffix matching.

These tests lock in the expected behavior for both new factories AND
verify the old factories still behave as documented (back-compat).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ormica import Ormica
from ormica.brain import MockBrain
from ormica.cortex.loader import build_rule
from ormica.cortex.rules import (
    banned_word_stems,
    banned_words,
    min_runtime_task_description,
    min_task_description,
)


# --- min_runtime_task_description --------------------------------------------


def test_min_runtime_task_description_passes_when_long_enough():
    rule = min_runtime_task_description(8)
    task = SimpleNamespace(description="This is a long enough brief")
    assert rule.check({"task": task}) is True


def test_min_runtime_task_description_rejects_short_brief():
    rule = min_runtime_task_description(20)
    task = SimpleNamespace(description="too short")
    assert rule.check({"task": task}) is False


def test_min_runtime_task_description_no_runtime_task_passes():
    """Agent driven directly (no runner) has ctx['task']=None — pre-stage
    rules should pass rather than spuriously fail when there's nothing
    to check against."""
    rule = min_runtime_task_description(50)
    assert rule.check({"task": None}) is True


def test_min_runtime_task_description_via_real_runner():
    """End-to-end: a task with too-short description gets rejected by the runner."""
    rule = min_runtime_task_description(15)
    from ormica.cortex import Constitution

    org = Ormica("X", max_depth=3, constitution=Constitution([rule]))
    org.spawn("worker", role="worker")
    org.task("brief", target="worker")  # 5 chars — too short
    result = org.run(brain=MockBrain(replies=["ok"]))
    assert result.failed == 1
    assert result.succeeded == 0


def test_min_task_description_still_reads_spawn_time_task_text():
    """Back-compat: the old factory keeps its documented semantics."""
    rule = min_task_description(8)
    # spawn-time task lives in ctx['task_text'], not ctx['task'].description.
    assert rule.check({"task_text": "long enough"}) is True
    assert rule.check({"task_text": "tiny"}) is False
    # Crucially, this rule does NOT consider ctx['task'].description.
    runtime_task = SimpleNamespace(description="a quite long runtime description")
    assert rule.check({"task_text": "", "task": runtime_task}) is False


def test_both_factories_registered_in_loader():
    """yaml `constitution.rules:` can name either factory."""
    r1 = build_rule({"min_task_description": 5})
    r2 = build_rule({"min_runtime_task_description": 5})
    assert r1.name == "min_task_description_5"
    assert r2.name == "min_runtime_task_description_5"


# --- banned_word_stems -------------------------------------------------------


def _ctx_with_response(content: str) -> dict:
    return {"response": SimpleNamespace(content=content)}


def test_banned_word_stems_catches_suffix_inflections():
    """The motivating case: a single stem catches all suffix-added forms."""
    rule = banned_word_stems(["guarantee"])
    # guarantee keeps its literal stem in every inflection — caught.
    for word in ("guarantee", "guarantees", "guaranteed", "guaranteeing"):
        assert rule.check(_ctx_with_response(f"We {word} results.")) is False, word


def test_banned_word_stems_silent_e_drop_is_a_known_gap():
    """English silent-e drop before -ing (cure→curing, approve→approving)
    is NOT handled — stem matching requires the literal stem to be present.
    Document the workaround: list both forms when this case matters."""
    only_stem = banned_word_stems(["cure"])
    # These work — stem is preserved.
    assert only_stem.check(_ctx_with_response("Cures acne")) is False
    assert only_stem.check(_ctx_with_response("Cured patients")) is False
    # This does NOT work — silent e dropped.
    assert only_stem.check(_ctx_with_response("Curing diabetes")) is True
    # Workaround: list both stems explicitly.
    both_stems = banned_word_stems(["cure", "curing"])
    assert both_stems.check(_ctx_with_response("Curing diabetes")) is False


def test_banned_word_stems_does_not_match_inside_other_words():
    """The trade-off vs banned_words: gain stem matching, lose substring."""
    rule = banned_word_stems(["guarantee"])
    # "unguaranteed" — substring contains guarantee but not as a whole word.
    # By design: whole-word boundary, so this passes.
    assert rule.check(_ctx_with_response("It was unguaranteed.")) is True


def test_banned_word_stems_case_insensitive():
    rule = banned_word_stems(["guarantee"])
    assert rule.check(_ctx_with_response("GUARANTEED")) is False
    assert rule.check(_ctx_with_response("Guaranteeing")) is False


def test_banned_word_stems_passes_clean_text():
    rule = banned_word_stems(["guarantee", "miracle"])
    assert rule.check(_ctx_with_response("Standard helpful response.")) is True


def test_banned_word_stems_rejects_empty_stems_list():
    """A rule that bans nothing always passes — almost certainly a bug."""
    with pytest.raises(ValueError, match="at least one non-empty stem"):
        banned_word_stems([])
    with pytest.raises(ValueError):
        banned_word_stems(["", "", ""])


def test_banned_word_stems_handles_regex_special_chars():
    """Stems with regex metachars (e.g. a literal period) must be escaped."""
    rule = banned_word_stems(["dr.", "u.s.a"])  # weird but valid input
    # Should not raise; should not match unrelated text.
    assert rule.check(_ctx_with_response("Hello there.")) is True


def test_banned_words_substring_behavior_unchanged():
    """Back-compat: the old factory keeps substring semantics, including
    the inflection blind spot that motivated banned_word_stems."""
    rule = banned_words(["guaranteed"])
    # Old rule does NOT catch "guaranteeing" (substring miss).
    assert rule.check(_ctx_with_response("guaranteeing")) is True
    # But DOES catch substring inside other words.
    assert rule.check(_ctx_with_response("UNGUARANTEED")) is False


def test_banned_word_stems_registered_in_loader():
    rule = build_rule({"banned_word_stems": ["guarantee", "miracle"]})
    assert rule.name.startswith("banned_word_stems_")
    assert rule.stage == "post"


# --- end-to-end: stems via real runner ---------------------------------------


def test_banned_word_stems_end_to_end_catches_inflection():
    """The whole reason this factory exists: a real run rejects an
    inflected form that the old banned_words would let through."""
    from ormica.cortex import Constitution

    org = Ormica(
        "X",
        max_depth=3,
        constitution=Constitution([banned_word_stems(["guarantee"])]),
    )
    org.spawn("writer", role="writer")
    org.task("Draft a caption", target="writer")
    # Mock emits an inflection of "guarantee" — should trip the rule.
    org.run(brain=MockBrain(replies=["This caption is guaranteeing 10k followers."]))
    assert org.tasks[0].status == "failed"
    assert "banned_word_stems" in (org.tasks[0].error or "")
