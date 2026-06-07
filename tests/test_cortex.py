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
from ormica.runtime import Task


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


def test_spawn_stage_context_exposes_role_and_task_text():
    """Spawn rules can reason about the child's role and task string (issue #5)."""
    seen: dict = {}

    def capture(ctx):
        seen.update(ctx)
        return ctx["role"] != "finance"

    constitution = Constitution([
        Rule(
            name="no_finance",
            description="block finance role at spawn",
            check=capture,
            stage="spawn",
            severity="hard",
        ),
    ])
    org = Ormica("HQ", constitution=constitution)

    org.spawn("ops", role="ops", task="run the floor")
    assert seen["role"] == "ops"
    assert seen["task_text"] == "run the floor"

    with pytest.raises(SpawnDenied):
        org.spawn("treasury", role="finance", task="manage cash")


def test_constitution_policy_composes_with_inner_policy():
    """If inner says no, ConstitutionPolicy says no — even when rules pass."""
    class AlwaysDenyInner:
        def allow(self, parent, child_name, **_):
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


def test_pre_stage_context_separates_task_object_from_task_text():
    """ctx["task"] is the runtime Task; ctx["task_text"] is the Node.task string (issue #6)."""
    seen: dict = {}

    constitution = Constitution([
        Rule(
            name="record_ctx",
            description="capture pre-stage context shape",
            check=lambda ctx: seen.update(ctx) or True,
        ),
    ])
    org = Ormica("HQ", constitution=constitution)
    org.spawn("scout", role="scout", task="watch the perimeter")
    org.task("look north", dept="scout", priority="high")

    org.run(brain=MockBrain(replies=["ok"]))

    assert seen["task_text"] == "watch the perimeter"
    assert isinstance(seen["task"], Task)
    assert seen["task"].description == "look north"
    assert seen["task"].priority == "high"


def test_pre_stage_task_is_none_when_agent_driven_directly():
    """Without a runner setting runtime_task, ctx["task"] is None (issue #6)."""
    seen: dict = {}
    constitution = Constitution([
        Rule(name="snap", description="", check=lambda ctx: seen.update(ctx) or True),
    ])
    org = Ormica("HQ")
    node = org.spawn("scout", role="scout", task="watch")
    agent = Agent(node, MockBrain(replies=["ok"]), constitution=constitution)
    agent.act("look")

    assert seen["task"] is None
    assert seen["task_text"] == "watch"


def test_post_stage_hard_rule_blocks_response_after_brain_call():
    """Hard post-stage rule fires after brain.think and raises before return.

    Brain IS called (tokens are real), but the response never leaves the agent
    when a post rule rejects it. Node state is FAILED.
    """
    constitution = Constitution([
        Rule(
            name="ban_secret",
            description="response must not mention 'secret'",
            check=lambda ctx: "secret" not in ctx["response"].content.lower(),
            stage="post",
        ),
    ])
    org = Ormica("HQ")
    node = org.spawn("scout", role="scout")
    brain = MockBrain(replies=["the secret is 42"])
    agent = Agent(node, brain, constitution=constitution)

    with pytest.raises(RuleViolation):
        agent.act("what's up")
    assert brain.calls != []  # brain WAS called — post is post
    assert node.state.value == "failed"


def test_post_stage_soft_rule_lets_response_through_but_records_violation():
    """Soft post-stage rules emit an event but don't block the response."""
    from ormica.observe import CollectObserver, RULE_SOFT_VIOLATION

    constitution = Constitution([
        Rule(
            name="prefer_short",
            description="responses should be short",
            check=lambda ctx: len(ctx["response"].content) <= 5,
            stage="post",
            severity="soft",
        ),
    ])
    org = Ormica("HQ", constitution=constitution)
    org.spawn("scout", role="scout")
    collected = CollectObserver()
    org.events.subscribe(collected)
    org.task("look", dept="scout")
    result = org.run(brain=MockBrain(replies=["a very long answer indeed"]))

    assert result.succeeded == 1
    assert result.failed == 0
    soft_events = [e for e in collected.events if e.type == RULE_SOFT_VIOLATION]
    assert len(soft_events) == 1
    assert soft_events[0].payload["rule"] == "prefer_short"
    assert soft_events[0].payload["stage"] == "post"


def test_post_stage_context_exposes_response_and_runtime_task():
    """Post-stage context schema: same as pre + `response`."""
    seen: dict = {}

    constitution = Constitution([
        Rule(
            name="capture",
            description="capture post-stage context",
            check=lambda ctx: seen.update(ctx) or True,
            stage="post",
        ),
    ])
    org = Ormica("HQ", constitution=constitution)
    org.spawn("scout", role="scout", task="watch")
    org.task("look north", dept="scout", priority="high")
    org.run(brain=MockBrain(replies=["all clear"]))

    assert seen["response"].content == "all clear"
    assert seen["task_text"] == "watch"
    assert isinstance(seen["task"], Task)
    assert seen["task"].description == "look north"
    assert seen["prompt"] == "look north"


def test_post_stage_fires_only_on_final_response_of_tool_loop():
    """In act_with_tools, intermediate tool-use responses don't trigger post-stage.

    The rule should see the user-visible final answer, not the model's
    decision to call a tool mid-loop.
    """
    from ormica.brain import ToolCall, tool

    seen_responses: list = []
    constitution = Constitution([
        Rule(
            name="capture_final",
            description="capture every post-stage response",
            check=lambda ctx: seen_responses.append(ctx["response"].content) or True,
            stage="post",
        ),
    ])

    @tool
    def ping() -> str:
        """Returns pong."""
        return "pong"

    org = Ormica("HQ")
    node = org.spawn("scout", role="scout")
    # First reply asks for a tool; second is plain text (the final answer).
    brain = MockBrain(replies=[[ToolCall(id="1", name="ping", arguments={})], "pinged"])
    agent = Agent(node, brain, constitution=constitution)

    response = agent.act_with_tools("ping it", tools=[ping])
    assert response.content == "pinged"
    assert seen_responses == ["pinged"]  # only the final response, not the tool-use turn


def test_run_loop_marks_task_failed_on_post_stage_hard_violation():
    """A hard post-stage violation in the runner path: task is failed, run continues."""
    constitution = Constitution([
        Rule(
            name="ban_secret",
            description="response must not mention 'secret'",
            check=lambda ctx: "secret" not in ctx["response"].content.lower(),
            stage="post",
        ),
    ])
    org = Ormica("HQ", constitution=constitution)
    org.spawn("scout", role="scout")
    org.spawn("hunter", role="hunter")
    org.task("hunt", dept="hunter")
    org.task("scout", dept="scout")
    # Brain replies in queue order: hunter first ("ok"), scout second ("the secret").
    # 'high' priority isn't set; alphabetic ordering doesn't apply — runtime sorts by
    # priority bands then created_at, so hunt (created first) runs first.
    result = org.run(brain=MockBrain(replies=["ok", "the secret"]))

    assert result.processed == 2
    assert result.succeeded == 1
    assert result.failed == 1
    by_target = {t.target: t for t in org.tasks}
    assert by_target["hunter"].status == "done"
    assert "RuleViolation" in by_target["scout"].error


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
