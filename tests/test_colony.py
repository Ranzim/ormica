"""Tests for the colony base layer — AgentTemplate, Colony, registry, facade hooks."""
import pytest

from ormica import Agent, Ormica
from ormica.arbor import NodeNotFound
from ormica.colony import AgentTemplate, Colony, colonies, register
from ormica.brain import MockBrain


def test_agent_template_plants_node_with_class_defaults():
    class Scout(AgentTemplate):
        name = "scout"
        role = "scout"
        task = "look around"
        system_prompt = "be observant"

    org = Ormica("HQ")
    node = Scout.plant(org)

    assert node.name == "scout"
    assert node.role == "scout"
    assert node.task == "look around"
    assert node.meta["system_prompt"] == "be observant"
    assert node.meta["template"] == "Scout"
    assert node.parent is org.root


def test_agent_template_plant_accepts_overrides():
    class Worker(AgentTemplate):
        name = "worker"
        role = "worker"
        task = "default task"

    org = Ormica("HQ")
    parent = org.spawn("ops")
    node = Worker.plant(org, under=parent, name="worker-7", task="urgent")

    assert node.parent is parent
    assert node.name == "worker-7"
    assert node.task == "urgent"
    assert node.role == "worker"  # role still comes from class


def test_agent_template_falls_back_to_class_name_when_unset():
    class CustomThing(AgentTemplate):
        pass

    org = Ormica("HQ")
    node = CustomThing.plant(org)
    assert node.name == "customthing"
    assert node.role == ""


def test_org_add_returns_planted_node():
    class Scout(AgentTemplate):
        name = "scout"
        role = "field"

    org = Ormica("HQ")
    node = org.add(Scout)

    assert node is org.find("scout")
    assert node.role == "field"


def test_org_plant_resolves_colony_by_name():
    org = Ormica("Acme")
    nodes = org.plant("business")

    assert len(nodes) == 4
    names = {n.name for n in nodes}
    assert names == {"operations", "sales", "marketing", "finance"}
    for node in nodes:
        assert node.parent is org.root


def test_org_plant_unknown_colony_raises():
    org = Ormica("Acme")
    with pytest.raises(KeyError, match="Unknown colony"):
        org.plant("does_not_exist")


def test_colonies_lists_registered_names():
    names = colonies()
    assert "business" in names
    assert "supply_chain" in names


def test_register_requires_non_empty_name():
    class Nameless(Colony):
        pass

    with pytest.raises(ValueError):
        register(Nameless)


def test_custom_colony_can_be_registered_and_resolved():
    class TinyColony(Colony):
        name = "test_tiny"

        def templates(self):
            class Tinybot(AgentTemplate):
                name = "tinybot"
                role = "tiny"

            return [Tinybot]

    register(TinyColony)
    try:
        org = Ormica("X")
        nodes = org.plant("test_tiny")
        assert [n.name for n in nodes] == ["tinybot"]
    finally:
        from ormica.colony.registry import _COLONIES

        _COLONIES.pop("test_tiny", None)


def test_planted_node_drives_agent_system_prompt():
    """An Agent built around a planted node picks up the template's prompt via meta."""

    class Quirky(AgentTemplate):
        name = "quirky"
        role = "quirky-role"
        task = "do quirky things"
        system_prompt = "Speak only in haiku."

    org = Ormica("HQ")
    node = org.add(Quirky)

    cortex = MockBrain(replies=["ok"])
    agent = Agent(node, cortex)
    agent.act("hi")

    system_msg = cortex.calls[0][0]
    assert system_msg.role == "system"
    assert "Speak only in haiku." in system_msg.content
    assert "Your role: quirky-role." in system_msg.content
    assert "Your task: do quirky things" in system_msg.content


def test_explicit_agent_system_prompt_overrides_meta():
    class Quirky(AgentTemplate):
        name = "quirky"
        system_prompt = "Default from template."

    org = Ormica("HQ")
    node = org.add(Quirky)
    cortex = MockBrain(replies=["ok"])
    agent = Agent(node, cortex, system_prompt="Override from caller.")
    agent.act("hi")

    text = cortex.calls[0][0].content
    assert "Override from caller." in text
    assert "Default from template." not in text


def test_find_locates_planted_department_by_name():
    org = Ormica("Acme")
    org.plant("business")
    # Sanity: each canonical name resolves.
    for dept in ("operations", "sales", "marketing", "finance"):
        org.find(dept)
    with pytest.raises(NodeNotFound):
        org.find("ghost")
