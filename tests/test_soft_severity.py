"""Tests for soft rule severity — declarable from yaml + recorded in trace.

Three layers:
  1. ``build_rule`` accepts ``severity: hard|soft`` in the spec mapping.
  2. Soft rules don't fail the task (existing Constitution behavior, locked in).
  3. ``TraceObserver`` captures ``rule.soft_violation`` events into
     ``Trace.warnings`` so ``ormica trace <id>`` and exporters can surface
     "shipped with warnings."
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ormica import Ormica
from ormica.brain import MockBrain
from ormica.cortex import Constitution
from ormica.cortex.loader import build_constitution, build_rule
from ormica.observe import TraceObserver


# --- build_rule severity hook ------------------------------------------------


def test_build_rule_defaults_to_hard():
    rule = build_rule({"max_response_tokens": 200})
    assert rule.severity == "hard"


def test_build_rule_accepts_soft_via_sibling_key():
    rule = build_rule({"max_response_tokens": 200, "severity": "soft"})
    assert rule.severity == "soft"
    # And other fields still come through correctly.
    assert rule.name.startswith("max_response_tokens_")
    assert rule.stage == "post"


def test_build_rule_accepts_explicit_hard():
    rule = build_rule({"max_response_tokens": 200, "severity": "hard"})
    assert rule.severity == "hard"


def test_build_rule_rejects_unknown_severity():
    with pytest.raises(ValueError, match="severity must be one of"):
        build_rule({"max_response_tokens": 200, "severity": "medium"})


def test_build_rule_rejects_multiple_factory_keys():
    """A mapping with severity + 2+ factory keys is ambiguous — error."""
    with pytest.raises(ValueError, match="two-key mapping"):
        build_rule({
            "max_response_tokens": 200,
            "min_response_length": 10,
            "severity": "soft",
        })


def test_build_rule_zero_arg_factory_with_soft():
    """Zero-arg factories work with severity too."""
    rule = build_rule({"require_json": None, "severity": "soft"})
    assert rule.severity == "soft"
    assert rule.name == "require_json"


def test_build_constitution_mixed_severities():
    constitution = build_constitution([
        {"max_response_tokens": 200, "severity": "soft"},
        {"max_response_tokens": 1000},
    ])
    rules = list(constitution)
    assert len(rules) == 2
    severities = {r.severity for r in rules}
    assert severities == {"soft", "hard"}


# --- runtime: soft rules don't fail the task --------------------------------


def test_soft_rule_violation_does_not_fail_task():
    """The defining contract: an overshooting response under a SOFT cap
    still ships; under a HARD cap of the same factory, it fails."""
    soft_constitution = Constitution([
        build_rule({"max_response_tokens": 5, "severity": "soft"}),
    ])
    org = Ormica("X", max_depth=3, constitution=soft_constitution)
    org.spawn("worker", role="worker")
    org.task("do something", target="worker")

    # MockBrain reply is long enough to overshoot 5 tokens (the rule fires
    # post-stage on response.tokens_used).
    result = org.run(brain=MockBrain(
        replies=["This is a deliberately long response that exceeds the cap."]
    ))
    assert result.succeeded == 1
    assert result.failed == 0


def test_hard_rule_violation_fails_task_for_comparison():
    """Sanity: the same factory at hard severity DOES fail."""
    hard_constitution = Constitution([
        build_rule({"max_response_tokens": 5}),  # default hard
    ])
    org = Ormica("X", max_depth=3, constitution=hard_constitution)
    org.spawn("worker", role="worker")
    org.task("do something", target="worker")
    result = org.run(brain=MockBrain(
        replies=["This is a deliberately long response that exceeds the cap."]
    ))
    assert result.failed == 1
    assert result.succeeded == 0


# --- trace recording ---------------------------------------------------------


def test_soft_violations_land_in_trace_warnings():
    """The audit story: a soft-rule fire should be visible on the Trace,
    so `ormica trace <id>` and exporters can surface 'shipped with warnings'."""
    soft = Constitution([
        build_rule({"max_response_tokens": 5, "severity": "soft"}),
    ])
    org = Ormica("X", max_depth=3, constitution=soft)
    org.spawn("worker", role="worker")
    org.subscribe(TraceObserver(store=org.memory))

    org.task("do something", target="worker")
    org.run(brain=MockBrain(replies=["This is a long reply that overshoots."]))

    trace = org.trace_for(org.tasks[0].id)
    assert trace.status == "done"
    assert len(trace.warnings) == 1
    w = trace.warnings[0]
    assert w["rule"].startswith("max_response_tokens_")
    assert w["stage"] == "post"
    assert "reason" in w


def test_no_warnings_when_no_soft_rules_fire():
    """Trace.warnings stays empty when soft rules pass (or no soft rules exist)."""
    org = Ormica("X", max_depth=3)
    org.spawn("worker", role="worker")
    org.subscribe(TraceObserver(store=org.memory))
    org.task("do something", target="worker")
    org.run(brain=MockBrain(replies=["ok"]))
    trace = org.trace_for(org.tasks[0].id)
    assert trace.warnings == []


def test_multiple_soft_violations_accumulate():
    """A task that trips two soft rules records both, in order."""
    soft = Constitution([
        build_rule({"max_response_tokens": 5, "severity": "soft"}),
        build_rule({"min_response_length": 1000, "severity": "soft"}),
    ])
    org = Ormica("X", max_depth=3, constitution=soft)
    org.spawn("worker", role="worker")
    org.subscribe(TraceObserver(store=org.memory))
    org.task("do something", target="worker")
    org.run(brain=MockBrain(replies=["short but over-token reply"]))
    trace = org.trace_for(org.tasks[0].id)
    assert len(trace.warnings) == 2
    rule_names = {w["rule"] for w in trace.warnings}
    assert any(n.startswith("max_response_tokens_") for n in rule_names)
    assert any(n.startswith("min_response_length_") for n in rule_names)


def test_hard_failure_still_records_any_prior_soft_warnings():
    """If a hard rule fails after a soft rule has fired in the same enforcement
    pass, the soft warning should still be on the (now-failed) trace.

    Note: Constitution.enforce raises on hard, so any soft violations from the
    SAME enforce() call may or may not be emitted depending on order. This
    test pins the contract for soft rules emitted in an EARLIER enforcement
    (pre-stage) when a LATER one (post-stage) hard-fails.
    """
    rules = [
        # Pre-stage soft rule that always fires
        build_rule({"min_runtime_task_description": 1000, "severity": "soft"}),
        # Post-stage hard rule that the response trips
        build_rule({"max_response_tokens": 5}),
    ]
    org = Ormica("X", max_depth=3, constitution=Constitution(rules))
    org.spawn("worker", role="worker")
    org.subscribe(TraceObserver(store=org.memory))
    org.task("brief", target="worker")  # short description → trips pre-soft
    org.run(brain=MockBrain(replies=["a deliberately long response over budget"]))
    trace = org.trace_for(org.tasks[0].id)
    assert trace.status == "failed"
    # Pre-stage soft fired before the post-stage hard raised.
    assert len(trace.warnings) >= 1
    assert any(w["stage"] == "pre" for w in trace.warnings)


# --- trace round-trips via mycelium ------------------------------------------


def test_trace_warnings_survive_mycelium_round_trip():
    """The Trace dataclass adds a default-empty `warnings` field; old persisted
    traces (without the key) still hydrate correctly."""
    org = Ormica("X", max_depth=3)
    org.spawn("worker", role="worker")
    org.subscribe(TraceObserver(store=org.memory))
    org.task("do something", target="worker")
    org.run(brain=MockBrain(replies=["ok"]))

    # Pull via the mycelium-backed path (not the in-memory observer cache).
    # core.trace_for reads from `traces/{task_id}` and rebuilds the Trace.
    persisted = org.trace_for(org.tasks[0].id)
    assert persisted is not None
    assert persisted.warnings == []  # default after round-trip


def test_old_persisted_trace_without_warnings_field_hydrates(tmp_path):
    """Back-compat: a trace written by an earlier version (no `warnings` key)
    must still be readable. Simulated by writing a dict that omits warnings."""
    from ormica.observe import Trace

    org = Ormica("X", max_depth=3, memory_db=str(tmp_path / "db.sqlite"))
    leaf = org.spawn("worker")
    # Manually write a trace dict that PREDATES the warnings field.
    org.memory.write(
        "traces/old-task-id",
        {
            "task_id": "old-task-id",
            "node_id": leaf.id,
            "target": "worker",
            "description": "legacy task",
            "started_at": 0.0,
            "ended_at": 1.0,
            "status": "done",
            "result": None,
            "error": None,
            "entries": [],
            # NOTE: no "warnings" key
        },
        author=leaf.id,
    )
    trace = org.trace_for("old-task-id")
    assert trace is not None
    assert isinstance(trace, Trace)
    assert trace.warnings == []   # default-applied
