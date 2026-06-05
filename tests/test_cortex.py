"""Tests for cortex — Rule, Constitution, ConstitutionPolicy, agent enforcement."""
import pytest

from ormica import Agent, Ormica
from ormica.arbor import SpawnDenied
from ormica.brain import MockBrain
from ormica.cortex import (
    Constitution,
    ConstitutionPolicy,
    Rule,
    RuleViolation,
    Violation,
)


# --- Rule basic semantics -----------------------------------------------------


def test_rule_passes_when_predicate_true():
    rule = Rule(
        name="under_limit",
        description="budget < 100",
        check=lambda ctx: ctx["used"] < 100,
    )
    assert rule.evaluate({"used": 50}) is None


def test_rule_returns_violation_when_predicate_false():
    rule = Rule(
        name="under_limit",
        description="budget < 100",
        check=lambda ctx: ctx["used"] < 100,
    )
    v = rule.evaluate({"used": 200})
    assert isinstance(v, Violation)
    assert v.rule is rule


def test_rule_exception_becomes_violation_not_crash():
    rule = Rule(
        name="boom",
        description="raises",
        check=lambda _ctx: 1 / 0,
    )
    v = rule.evaluate({})
    assert v is not None
    assert "ZeroDivisionError" in v.reason


def test_rule_str_format_is_useful():
    rule = Rule(name="X", description="", check=lambda _: False)
    v = rule.evaluate({})
    assert str(v) == "X: check returned False"


# --- Constitution -------------------------------------------------------------


def test_constitution_returns_empty_when_no_rules_violated():
    c = Constitution([
        Rule(name="ok", description="", check=lambda _: True),
    ])
    assert c.check({}) == []


def test_constitution_aggregates_all_violations():
    c = Constitution([
        Rule(name="a", description="", check=lambda _: False),
        Rule(name="b", description="", check=lambda _: False),
        Rule(name="c", description="", check=lambda _: True),
    ])
    violations = c.check({})
    assert [v.rule.name for v in violations] == ["a", "b"]


def test_constitution_enforce_raises_on_hard_violation():
    c = Constitution([
        Rule(name="hard_rule", description="", check=lambda _: False, severity="hard"),
    ])
    with pytest.raises(RuleViolation):
        c.enforce({})


def test_constitution_enforce_returns_soft_violations_without_raising():
    c = Constitution([
        Rule(name="soft1", description="", check=lambda _: False, severity="soft"),
        Rule(name="hard1", description="", check=lambda _: True, severity="hard"),
    ])
    soft = c.enforce({})
    assert len(soft) == 1
    assert soft[0].rule.name == "soft1"


def test_constitution_stages_filter_evaluation():
    c = Constitution([
        Rule(name="pre_rule", description="", check=lambda _: False, stage="pre"),
        Rule(name="post_rule", description="", check=lambda _: False, stage="post"),
    ])
    assert [v.rule.name for v in c.check({}, stage="pre")] == ["pre_rule"]
    assert [v.rule.name for v in c.check({}, stage="post")] == ["post_rule"]


def test_constitution_add_appends_rule():
    c = Constitution()
    assert len(c) == 0
    c.add(Rule(name="x", description="", check=lambda _: True))
    assert len(c) == 1


# --- ConstitutionPolicy -------------------------------------------------------


def test_spawn_policy_denies_when_rule_fails_at_spawn_stage():
    constitution = Constitution([
        Rule(
            name="max_depth_2",
            description="tree may not grow past depth 2",
            check=lambda ctx: ctx["depth"] <= 2,
            stage="spawn",
        ),
    ])
    policy = ConstitutionPolicy(constitution)

    org = Ormica("HQ", policy=policy)
    org.spawn("a")  # depth 1 — allowed
    a = org.find("a")
    org.tree.spawn(a, "b")  # depth 2 — allowed

    b = org.find("b")
    with pytest.raises(SpawnDenied):
        org.tree.spawn(b, "c")  # depth 3 — blocked


def test_constitution_via_ormica_facade_governs_spawn():
    """Passing constitution= to Ormica wraps it as the SpawnPolicy."""
    constitution = Constitution([
        Rule(
            name="no_finance",
            description="cannot spawn a 'finance' node",
            check=lambda ctx: ctx["child_name"] != "finance",
            stage="spawn",
        ),
    ])
    org = Ormica("Acme", constitution=constitution)
    org.spawn("ops")  # allowed
    with pytest.raises(SpawnDenied):
        org.spawn("finance")


def test_constitution_policy_composes_with_inner_policy():
    """If inner says no, ConstitutionPolicy says no — even when rules pass."""
    class AlwaysDenyInner:
        def allow(self, parent, child_name):
            return False

    policy = ConstitutionPolicy(Constitution(), inner=AlwaysDenyInner())
    org = Ormica("X", policy=policy)
    with pytest.raises(SpawnDenied):
        org.spawn("anything")


# --- Agent enforcement at runtime ---------------------------------------------


def test_agent_enforces_constitution_before_brain_call():
    constitution = Constitution([
        Rule(
            name="no_finance_role",
            description="finance role can't think",
            check=lambda ctx: ctx["role"] != "finance",
        ),
    ])
    org = Ormica("HQ")
    node = org.spawn("finance", role="finance")
    brain = MockBrain(replies=["should not be called"])
    agent = Agent(node, brain, constitution=constitution)

    with pytest.raises(RuleViolation):
        agent.act("hi")
    assert brain.calls == []  # brain never called


def test_agent_act_proceeds_when_rules_pass():
    constitution = Constitution([
        Rule(name="ok", description="", check=lambda _ctx: True),
    ])
    org = Ormica("HQ")
    node = org.spawn("scout", role="scout")
    agent = Agent(node, MockBrain(replies=["scouted"]), constitution=constitution)
    assert agent.act("look").content == "scouted"


def test_agent_without_constitution_unaffected():
    """A None constitution is the default — no enforcement, no errors."""
    org = Ormica("HQ")
    node = org.spawn("scout")
    agent = Agent(node, MockBrain(replies=["ok"]))
    assert agent.act("hi").content == "ok"


def test_run_loop_marks_task_failed_on_rule_violation():
    """If a task's agent violates a hard rule, the task fails — run keeps going."""
    constitution = Constitution([
        Rule(
            name="no_ghost_targets",
            description="don't target the 'ghost' role",
            check=lambda ctx: ctx["role"] != "ghost",
        ),
    ])
    org = Ormica("HQ", constitution=constitution)
    org.spawn("ghost", role="ghost")
    org.spawn("scout", role="scout")
    org.task("haunt", dept="ghost")
    org.task("scout area", dept="scout")

    result = org.run(brain=MockBrain(replies=["ok"]))
    assert result.processed == 2
    assert result.succeeded == 1
    assert result.failed == 1
    by_target = {t.target: t for t in org.tasks}
    assert "RuleViolation" in by_target["ghost"].error
    assert by_target["scout"].status == "done"
