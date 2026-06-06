"""Tests for the tool-use abstraction — @tool, ToolCall, Agent.act_with_tools."""
import pytest

from ormica import Agent, AsyncAgent, Ormica
from ormica.agent import ToolLoopExceeded
from ormica.arbor import Tree
from ormica.brain import (
    AsyncMockBrain,
    MockBrain,
    Tool,
    ToolCall,
    tool,
)


# --- @tool decorator ----------------------------------------------------------


def test_tool_decorator_builds_schema_from_signature():
    @tool
    def get_weather(city: str, unit: str = "celsius") -> str:
        """Look up the current weather in a city."""
        return f"sunny in {city}"

    assert isinstance(get_weather, Tool)
    assert get_weather.name == "get_weather"
    assert get_weather.description == "Look up the current weather in a city."
    assert get_weather.schema == {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "unit": {"type": "string"},
        },
        "required": ["city"],
    }


def test_tool_decorator_supports_explicit_name_and_description():
    @tool(name="weather", description="Get weather.")
    def get_weather(city: str) -> str:
        return city

    assert get_weather.name == "weather"
    assert get_weather.description == "Get weather."


def test_tool_callable_runs_underlying_function():
    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    assert add(a=2, b=3) == 5


def test_tool_schema_supports_basic_types():
    @tool
    def mix(a: str, b: int, c: float, d: bool, e: list, f: dict) -> str:
        """Mix."""
        return "ok"

    types = {k: v["type"] for k, v in mix.schema["properties"].items()}
    assert types == {
        "a": "string",
        "b": "integer",
        "c": "number",
        "d": "boolean",
        "e": "array",
        "f": "object",
    }


# --- act_with_tools (sync) ----------------------------------------------------


def _make_agent() -> tuple[Tree, Agent]:
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    return tree, Agent(node, MockBrain(replies=["never used"]))


def test_act_with_tools_short_circuits_when_no_tool_calls():
    tree, agent = _make_agent()
    agent.brain = MockBrain(replies=["direct answer"])

    @tool
    def lookup(query: str) -> str:
        """Look something up."""
        return "data"

    response = agent.act_with_tools("hello", tools=[lookup])
    assert response.content == "direct answer"
    assert response.tool_calls == []


def test_act_with_tools_executes_requested_tool_and_loops():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    calls_made: list[dict] = []

    @tool
    def add(a: int, b: int) -> int:
        """Add."""
        calls_made.append({"a": a, "b": b})
        return a + b

    brain = MockBrain(
        replies=[
            [ToolCall(id="t1", name="add", arguments={"a": 2, "b": 3})],
            "the sum is 5",
        ]
    )
    agent = Agent(node, brain)
    response = agent.act_with_tools("compute 2+3", tools=[add])

    assert response.content == "the sum is 5"
    assert calls_made == [{"a": 2, "b": 3}]
    # Second think call must include the tool result in history.
    assert len(brain.calls) == 2
    second_history = brain.calls[1]
    assert any(m.role == "assistant" and m.tool_calls for m in second_history)
    assert any(m.role == "tool" and m.tool_call_id == "t1" for m in second_history)


def test_act_with_tools_passes_tools_through_to_cortex():
    tree, agent = _make_agent()

    @tool
    def thing(x: str) -> str:
        """Thing."""
        return x

    agent.brain = MockBrain(replies=["done"])
    agent.act_with_tools("hi", tools=[thing])
    assert agent.brain.tools_seen[0] == [thing]


def test_act_with_tools_handles_unknown_tool_name():
    """A tool the registry doesn't know about gets an error result, not a crash."""
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    brain = MockBrain(
        replies=[
            [ToolCall(id="t1", name="ghost", arguments={})],
            "I gave up",
        ]
    )
    agent = Agent(node, brain)

    @tool
    def real(x: str) -> str:
        """Real tool."""
        return x

    response = agent.act_with_tools("go", tools=[real])
    assert response.content == "I gave up"
    second_history = brain.calls[1]
    tool_msg = next(m for m in second_history if m.role == "tool")
    assert "unknown tool" in tool_msg.content


def test_act_with_tools_records_tool_exception_as_result():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")

    @tool
    def divide(a: int, b: int) -> float:
        """Divide a by b."""
        return a / b

    brain = MockBrain(
        replies=[
            [ToolCall(id="t1", name="divide", arguments={"a": 1, "b": 0})],
            "cannot divide by zero",
        ]
    )
    agent = Agent(node, brain)
    response = agent.act_with_tools("divide 1 by 0", tools=[divide])

    tool_msg = next(m for m in brain.calls[1] if m.role == "tool")
    assert "ZeroDivisionError" in tool_msg.content
    assert response.content == "cannot divide by zero"


def test_act_with_tools_raises_when_loop_exceeds_max_iterations():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")

    @tool
    def echo(x: str) -> str:
        """Echo."""
        return x

    # Reply is always a tool call — loop should hit max_iterations.
    def always_call(_messages):
        return [ToolCall(id="t", name="echo", arguments={"x": "y"})]

    brain = MockBrain(reply_fn=always_call)
    agent = Agent(node, brain)
    with pytest.raises(ToolLoopExceeded):
        agent.act_with_tools("loop forever", tools=[echo], max_iterations=3)


# --- act_with_tools (async) ---------------------------------------------------


@pytest.mark.asyncio
async def test_async_act_with_tools_loops():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")

    @tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    brain = AsyncMockBrain(
        replies=[
            [ToolCall(id="t1", name="add", arguments={"a": 4, "b": 5})],
            "result is 9",
        ]
    )
    agent = AsyncAgent(node, brain)
    response = await agent.act_with_tools("4+5?", tools=[add])
    assert response.content == "result is 9"
    second_history = brain.calls[1]
    assert any(m.role == "tool" and m.tool_call_id == "t1" for m in second_history)


@pytest.mark.asyncio
async def test_async_act_with_tools_max_iterations_exceeded():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")

    @tool
    def x(y: str) -> str:
        """X."""
        return y

    async def always(_messages):
        return [ToolCall(id="t", name="x", arguments={"y": "z"})]

    brain = AsyncMockBrain(reply_fn=always)
    agent = AsyncAgent(node, brain)
    with pytest.raises(ToolLoopExceeded):
        await agent.act_with_tools("loop", tools=[x], max_iterations=2)


# --- End-to-end via the facade ------------------------------------------------


def test_end_to_end_sync_tool_use_via_org():
    """A planted colony node calls a tool. Tool results land in memory."""
    org = Ormica("Acme")
    org.plant("business")
    sales = org.find("sales")

    @tool
    def lookup_lead(name: str) -> str:
        """Look up a lead by name."""
        return f"{name}: hot, demo booked"

    brain = MockBrain(
        replies=[
            [ToolCall(id="t1", name="lookup_lead", arguments={"name": "Acme Corp"})],
            "Final: Acme Corp is hot — demo booked.",
        ]
    )
    agent = Agent(sales, brain, memory=org.memory)
    response = agent.act_with_tools(
        "Should we pursue Acme Corp?", tools=[lookup_lead]
    )
    assert response.content.startswith("Final:")
