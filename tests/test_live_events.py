"""Tests for live activity events: node.spawned/pruned + memory.read/write.

These feed the live graph + log view — the engine emitting what it does as it
does it.
"""
from ormica import Agent, Ormica
from ormica.arbor import Tree
from ormica.brain import MockBrain
from ormica.mycelium import InMemoryBackend, InMemorySemanticBackend, Mycelium
from ormica.observe import (
    MEMORY_READ,
    MEMORY_WRITE,
    NODE_PRUNED,
    NODE_SPAWNED,
    CollectObserver,
    EventBus,
)


def _org_with_collector():
    org = Ormica("Acme")
    collector = CollectObserver()
    org.subscribe(collector)
    return org, collector


def _of(collector, event_type):
    return [e for e in collector.events if e.type == event_type]


# --- spawn / prune events -----------------------------------------------------


def test_spawn_emits_node_spawned_with_parentage():
    org, c = _org_with_collector()
    node = org.spawn("sales")
    [ev] = _of(c, NODE_SPAWNED)
    assert ev.payload["node_id"] == node.id
    assert ev.payload["name"] == "sales"
    assert ev.payload["parent_name"] == org.root.name
    assert ev.payload["depth"] == 1


def test_planting_a_colony_emits_one_spawn_per_node():
    org, c = _org_with_collector()
    org.plant("business")
    spawned = _of(c, NODE_SPAWNED)
    # every planted node announced itself
    assert len(spawned) == sum(1 for _ in org) - 1  # minus the root
    names = {e.payload["name"] for e in spawned}
    assert {"operations", "sales", "marketing", "finance"} <= names


def test_prune_emits_node_pruned_with_count():
    org, c = _org_with_collector()
    parent = org.spawn("dept")
    org.spawn("worker", under=parent)
    removed = org.prune(parent)
    [ev] = _of(c, NODE_PRUNED)
    assert ev.payload["removed"] == removed == 2  # dept + worker


def test_tree_hook_is_optional_and_exception_safe():
    # No hook: plain Tree still works.
    plain = Tree("HQ")
    assert plain.spawn(plain.root, "x").name == "x"

    # A raising hook must not break spawning.
    def boom_hook(_node):
        raise RuntimeError("observer blew up")

    boom = Tree("HQ", on_spawn=boom_hook)
    child = boom.spawn(boom.root, "survivor")
    assert child.name == "survivor"


# --- memory events ------------------------------------------------------------


def _agent_with_bus(memory):
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    agent = Agent(node, MockBrain(replies=["x"]), memory=memory)
    bus = EventBus()
    collector = CollectObserver()
    bus.subscribe(collector)
    agent.events = bus
    agent.task_id = "t1"
    return agent, collector, node


def test_remember_emits_memory_write():
    agent, c, node = _agent_with_bus(Mycelium(InMemoryBackend()))
    agent.remember("finding:1", "the cache has a race")
    [ev] = _of(c, MEMORY_WRITE)
    assert ev.payload["key"] == "finding:1"
    assert ev.payload["node"] == node.id
    assert ev.payload["task_id"] == "t1"


def test_recall_emits_memory_read_with_hit_flag():
    mem = Mycelium(InMemoryBackend())
    agent, c, _ = _agent_with_bus(mem)
    agent.remember("k", "v")
    agent.recall("k")
    agent.recall("missing")
    reads = _of(c, MEMORY_READ)
    assert reads[0].payload["hit"] is True
    assert reads[1].payload["hit"] is False


def test_recall_relevant_emits_memory_read_with_query():
    agent, c, _ = _agent_with_bus(Mycelium(InMemorySemanticBackend()))
    agent.remember("k", "distributed systems coordination")
    agent.recall_relevant("coordination", k=3)
    read = _of(c, MEMORY_READ)[-1]
    assert read.payload["query"] == "coordination"
    assert read.payload["k"] == 3
    assert read.payload["hits"] >= 1


def test_memory_events_are_noops_without_a_bus():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    agent = Agent(node, MockBrain(replies=["x"]), memory=Mycelium(InMemoryBackend()))
    # No agent.events set → must not raise.
    agent.remember("k", "v")
    assert agent.recall("k") == "v"
