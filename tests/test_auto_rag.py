"""Tests for auto-RAG — relevant memory auto-injected into the system prompt."""
import pytest

from ormica import Agent, AsyncAgent
from ormica.arbor import Tree
from ormica.brain import AsyncMockBrain, MockBrain
from ormica.mycelium import InMemoryBackend, InMemorySemanticBackend, Mycelium


def _mem_with(entries):
    mem = Mycelium(InMemorySemanticBackend())
    for k, v in entries:
        mem.write(k, v)
    return mem


def _system_seen(brain):
    """Extract the system message the brain saw on its first call."""
    msgs = brain.calls[0]
    sys = [m for m in msgs if m.role == "system"]
    return sys[0].content if sys else ""


def test_relevant_memory_injected_into_system_prompt():
    mem = _mem_with([
        ("finding:cache", "the flaky test is a race in the cache layer"),
        ("finding:sales", "enterprise upsells drove Q3 revenue"),
    ])
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "eng")
    agent = Agent(node, MockBrain(replies=["done"]), memory=mem, auto_recall=1)
    agent.act("why is the test flaky cache race")
    sys = _system_seen(agent.brain)
    assert "Relevant knowledge" in sys
    assert "flaky test is a race" in sys       # the relevant one was injected


def test_auto_recall_off_by_default():
    mem = _mem_with([("k", "some knowledge")])
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "eng")
    agent = Agent(node, MockBrain(replies=["done"]), memory=mem)  # auto_recall=0
    agent.act("anything")
    assert "Relevant knowledge" not in _system_seen(agent.brain)


def test_internal_keys_excluded():
    mem = _mem_with([("finding:x", "real knowledge about widgets")])
    # simulate internal writes that must NOT surface via auto-RAG
    mem.write("stigma/topic", {"strength": 1.0})
    mem.write("tasks/abc", {"status": "done"})
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "eng")
    agent = Agent(node, MockBrain(replies=["done"]), memory=mem, auto_recall=5)
    agent.act("widgets knowledge")
    sys = _system_seen(agent.brain)
    assert "finding:x" in sys
    assert "stigma/" not in sys and "tasks/" not in sys


def test_non_searchable_backend_is_noop():
    mem = Mycelium(InMemoryBackend())  # not searchable
    mem.write("k", "v")
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "eng")
    agent = Agent(node, MockBrain(replies=["done"]), memory=mem, auto_recall=3)
    agent.act("q")  # must not raise
    assert "Relevant knowledge" not in _system_seen(agent.brain)


def test_auto_recall_from_node_meta():
    mem = _mem_with([("finding:y", "distributed consensus notes")])
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "eng")
    node.meta["auto_recall"] = 2                # colony-declared
    agent = Agent(node, MockBrain(replies=["done"]), memory=mem)
    agent.act("consensus")
    assert "distributed consensus" in _system_seen(agent.brain)


def test_works_in_tool_loop_and_async():
    mem = _mem_with([("finding:z", "the pricing table: Growth 499, Scale 2499")])
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "eng")
    agent = Agent(node, MockBrain(replies=["ok"]), memory=mem, auto_recall=1)
    agent.act("what is the pricing")
    assert "pricing table" in _system_seen(agent.brain)


@pytest.mark.asyncio
async def test_async_auto_rag():
    mem = _mem_with([("finding:async", "the deploy runbook lives in ops/deploy.md")])
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "ops")
    agent = AsyncAgent(node, AsyncMockBrain(replies=["done"]), memory=mem, auto_recall=1)
    await agent.act("where is the deploy runbook")
    assert "deploy runbook" in _system_seen(agent.brain)
