"""Tests for the ergonomic helpers: Ormica.agent() and Ormica.ask()."""
from ormica import Ormica
from ormica.brain import MockBrain
from ormica.brain.tool import tool
from ormica.cortex import Constitution


# --- org.agent(): a fully-wired Agent with no manual plumbing -----------------


def test_agent_is_wired_to_the_colony():
    org = Ormica("Acme")
    node = org.spawn("scout")
    a = org.agent(node, brain=MockBrain(replies=["x"]))
    assert a.node is node
    assert a.memory is org.memory
    assert a.signals is org.signals
    assert a.constitution is org.constitution
    assert a.budget is org.budget
    assert a.events is org.events            # the line everyone forgets, done for you


def test_agent_defaults_to_root_and_resolves_names():
    org = Ormica("Acme")
    dept = org.spawn("sales", role="dept")
    assert org.agent(brain=MockBrain(replies=["x"])).node is org.root
    assert org.agent("sales", brain=MockBrain(replies=["x"])).node is dept


def test_agent_kwargs_override_colony_defaults():
    org = Ormica("Acme")
    node = org.spawn("a")
    con = Constitution([])
    a = org.agent(node, brain=MockBrain(replies=["x"]), constitution=con,
                  auto_recall=3, system_prompt="be terse")
    assert a.constitution is con             # caller override wins
    assert a.auto_recall == 3
    assert a.system_prompt == "be terse"


def test_agent_can_act():
    org = Ormica("Acme")
    org.spawn("worker")
    a = org.agent("worker", brain=MockBrain(replies=["done"]))
    assert a.act("do it").content == "done"


# --- org.ask(): one call, text back -------------------------------------------


def test_ask_returns_text_from_root():
    org = Ormica("Acme")
    assert org.ask("hello?", brain=MockBrain(replies=["hi there"])) == "hi there"


def test_ask_targets_a_named_node():
    org = Ormica("Acme")
    org.spawn("analyst", role="analyst")
    out = org.ask("analyse", brain=MockBrain(replies=["analysed"]), target="analyst")
    assert out == "analysed"


def test_ask_passes_declared_node_tools_automatically():
    org = Ormica("Acme")
    node = org.spawn("worker")

    @tool
    def ping() -> str:
        """ping."""
        return "pong"

    org.give_tools(node, [ping])
    brain = MockBrain(replies=["ok"])
    org.ask("go", brain=brain, target="worker")
    # the node's custom tool was handed to the brain without the caller wiring it
    assert brain.tools_seen and brain.tools_seen[0] is not None
    assert any(getattr(t, "name", "") == "ping" for t in brain.tools_seen[0])


def test_ask_without_tools_uses_plain_act():
    org = Ormica("Acme")
    brain = MockBrain(replies=["plain"])
    assert org.ask("hi", brain=brain) == "plain"
    assert brain.tools_seen[0] is None       # no tools declared → plain act
