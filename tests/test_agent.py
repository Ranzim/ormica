"""Tests for the Agent — Node + Brain bridge."""
import pytest

from ormica import Agent
from ormica.arbor import NodeState, Tree
from ormica.brain import BudgetExhausted, MockBrain, TokenBudget
from ormica.mycelium import Mycelium
from ormica.stigma import Stigma


def _make(role: str = "", task: str = "", system: str = "", **kw):
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "scout", role=role, task=task)
    brain = MockBrain(replies=["ok"])
    return node, brain, Agent(node, brain, system_prompt=system, **kw)


def test_act_returns_cortex_response_and_marks_done():
    node, _, agent = _make()
    assert node.state == NodeState.IDLE

    resp = agent.act("hello")
    assert resp.content == "ok"
    assert node.state == NodeState.DONE


def test_failed_cortex_marks_node_failed_and_reraises():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "scout")

    def boom(messages):
        raise RuntimeError("kaboom")

    agent = Agent(node, MockBrain(reply_fn=boom))
    with pytest.raises(RuntimeError, match="kaboom"):
        agent.act("hi")
    assert node.state == NodeState.FAILED


def test_system_prompt_combines_role_task_and_explicit_text():
    node, brain, agent = _make(
        role="scout",
        task="find leads",
        system="Always be brief.",
    )
    agent.act("go")

    messages = brain.calls[0]
    assert messages[0].role == "system"
    sys_text = messages[0].content
    assert "Always be brief." in sys_text
    assert "Your role: scout." in sys_text
    assert "Your task: find leads" in sys_text


def test_no_system_message_when_nothing_to_say():
    node, brain, agent = _make()
    agent.act("hi")
    # First (and only) message should be the user prompt — no system header.
    assert brain.calls[0][0].role == "user"


def test_budget_consumed_after_each_act():
    node, brain, agent = _make(budget=TokenBudget(limit=1000))
    agent.act("first")
    used_after_one = agent.budget.used
    assert used_after_one > 0

    agent.act("second")
    assert agent.budget.used > used_after_one


def test_budget_exhausted_raises_before_calling_cortex():
    node, brain, agent = _make(budget=TokenBudget(limit=10, used=10))
    with pytest.raises(BudgetExhausted):
        agent.act("nope")
    assert brain.calls == []


def test_remember_and_recall_use_mycelium():
    mem = Mycelium()
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "scout")
    agent = Agent(node, MockBrain(replies=["x"]), memory=mem)

    agent.remember("found", "acme")
    assert agent.recall("found") == "acme"
    entry = mem.read("found")
    assert entry.author == node.id


def test_remember_and_recall_are_noops_without_memory():
    node, _, agent = _make()
    agent.remember("k", "v")  # no exception
    assert agent.recall("k", default=99) == 99


def test_emit_and_sense_use_stigma_when_wired():
    mem = Mycelium()
    stig = Stigma(mem, half_life=1e9)
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "scout")
    agent = Agent(node, MockBrain(replies=["x"]), signals=stig)

    agent.emit("found_food", strength=2.0)
    agent.reinforce("found_food", amount=1.0)
    sensed = agent.sense("found_food")

    assert sensed.strength == pytest.approx(3.0)
    assert sensed.sources == {node.id}


def test_signal_methods_are_noops_without_stigma():
    node, _, agent = _make()
    agent.emit("topic")
    agent.reinforce("topic")
    assert agent.sense("topic") is None


def test_soft_rule_emits_event_on_event_bus():
    """Soft constitution rules must surface to the org's event bus.

    Regression for the silent-drop bug: Agent._enforce_constitution used
    to call Constitution.enforce(...) and throw away the returned soft
    violation list, so severity="soft" rules fired invisibly.
    """
    from ormica import Ormica
    from ormica.cortex import Constitution, Rule
    from ormica.observe import CollectObserver, RULE_SOFT_VIOLATION

    constitution = Constitution([
        Rule(
            name="always_soft_fails",
            description="A soft rule that always returns False.",
            check=lambda _ctx: False,
            stage="pre",
            severity="soft",
        ),
    ])
    org = Ormica("soft-rule test", constitution=constitution)
    org.plant("business")
    collected = CollectObserver()
    org.events.subscribe(collected)
    org.task("noop", dept="sales")
    org.run(brain=MockBrain(replies=["ok"]))

    soft_events = [e for e in collected.events if e.type == RULE_SOFT_VIOLATION]
    assert len(soft_events) == 1
    assert soft_events[0].payload["rule"] == "always_soft_fails"
    assert soft_events[0].payload["node"] == "sales"
