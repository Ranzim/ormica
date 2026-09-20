"""Native async tools: awaited in the async loop, sync tools don't block it."""
import asyncio

import pytest

from ormica import Agent, AsyncAgent
from ormica.arbor import Tree
from ormica.brain import AsyncMockBrain, MockBrain, Tool, ToolCall, tool


@tool
def sync_add(a: int, b: int) -> int:
    """Add."""
    return a + b


def _async_agent(brain):
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    return AsyncAgent(node, brain)


@pytest.mark.asyncio
async def test_async_tool_is_awaited():
    async def _lookup(q: str) -> str:
        await asyncio.sleep(0)
        return f"async result for {q}"

    lookup = Tool(name="lookup", description="Look up.", fn=_lookup,
                  schema={"type": "object", "properties": {"q": {"type": "string"}},
                          "required": ["q"]})
    brain = AsyncMockBrain(replies=[
        [ToolCall(id="t1", name="lookup", arguments={"q": "x"})],
        "done",
    ])
    agent = _async_agent(brain)
    resp = await agent.act_with_tools("go", tools=[lookup])
    assert resp.content == "done"
    tool_msg = next(m for m in brain.calls[1] if m.role == "tool")
    assert tool_msg.content == "async result for x"   # coroutine was awaited


@pytest.mark.asyncio
async def test_sync_tool_runs_without_blocking_the_loop():
    # A blocking sync tool must run off the event loop (asyncio.to_thread),
    # so another coroutine keeps making progress while it "blocks".
    ticks = {"n": 0}

    async def ticker():
        for _ in range(5):
            await asyncio.sleep(0.01)
            ticks["n"] += 1

    def slow_tool() -> str:
        import time
        time.sleep(0.06)          # blocking — would freeze the loop if run inline
        return "slow done"

    st = Tool(name="slow", description="Slow.", fn=slow_tool,
              schema={"type": "object", "properties": {}})
    brain = AsyncMockBrain(replies=[[ToolCall(id="t1", name="slow", arguments={})], "ok"])
    agent = _async_agent(brain)
    bg = asyncio.create_task(ticker())
    await agent.act_with_tools("go", tools=[st])
    await bg
    assert ticks["n"] >= 3        # the ticker advanced while the tool "blocked"


@pytest.mark.asyncio
async def test_async_tool_exception_surfaces():
    async def boom() -> str:
        raise ValueError("nope")

    bt = Tool(name="boom", description="Boom.", fn=boom,
              schema={"type": "object", "properties": {}})
    brain = AsyncMockBrain(replies=[[ToolCall(id="t1", name="boom", arguments={})], "handled"])
    agent = _async_agent(brain)
    await agent.act_with_tools("go", tools=[bt])
    tool_msg = next(m for m in brain.calls[1] if m.role == "tool")
    assert "ValueError" in tool_msg.content


def test_sync_agent_rejects_async_tool_cleanly():
    async def at() -> str:
        return "x"

    atool = Tool(name="at", description="A.", fn=at, schema={"type": "object", "properties": {}})
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    brain = MockBrain(replies=[[ToolCall(id="t1", name="at", arguments={})], "gave up"])
    agent = Agent(node, brain)
    agent.act_with_tools("go", tools=[atool])
    tool_msg = next(m for m in brain.calls[1] if m.role == "tool")
    assert "async tool" in tool_msg.content       # clear error, no coroutine leak


def test_sync_tools_still_work_in_sync_loop():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    brain = MockBrain(replies=[
        [ToolCall(id="t1", name="sync_add", arguments={"a": 2, "b": 3})],
        "the sum is 5",
    ])
    agent = Agent(node, brain)
    assert agent.act_with_tools("2+3?", tools=[sync_add]).content == "the sum is 5"
