"""Tests for per-node custom-tool wiring (Ormica.give_tools)."""
import pytest

from ormica import Ormica, Task
from ormica.brain import AsyncMockBrain, MockBrain, ToolCall, tool
from ormica.runtime import _build_tools
from ormica.sandbox import Sandbox, SandboxLimits, python_tool


@tool
def ping() -> str:
    """Return pong."""
    return "pong"


# --- registration -------------------------------------------------------------


def test_give_tools_by_name_and_node():
    org = Ormica("Acme")
    org.spawn("worker")
    affected = org.give_tools("worker", [ping])
    assert len(affected) == 1
    assert org.tools_for("worker")[0].name == "ping"


def test_give_tools_composes_with_message_tool():
    from ormica.postbox import MessageToolConfig

    org = Ormica("Acme")
    org.spawn("sales")
    node = org.spawn("eng")
    node.meta["message_tool_config"] = MessageToolConfig(recipients=("sales",))
    org.give_tools("eng", [ping])

    names = {t.name for t in _build_tools(org, node)}
    assert names == {"send_message", "ping"}


# --- runner uses them ---------------------------------------------------------


def test_runner_passes_custom_tool_and_math_runs_for_real():
    org = Ormica("Acme")
    org.spawn("analyst")
    org.give_tools("analyst", [python_tool(Sandbox(SandboxLimits(timeout_sec=10)))])
    org.task("compute the product", target="analyst")

    brain = MockBrain(replies=[
        [ToolCall(id="c1", name="run_python", arguments={"code": "print(6 * 7)"})],
        "the product is 42",
    ])
    result = org.run(brain=brain)
    assert result.succeeded == 1
    # The sandbox really executed: the tool result carried 42.
    record = org.read(f"tasks/{org.tasks[0].id}")
    assert record.value["result"] == "the product is 42"


# --- real end-to-end DAG: sandbox compute -> result passed downstream ---------


@pytest.mark.asyncio
async def test_dag_real_compute_then_downstream_receives_result():
    org = Ormica("Acme")
    org.spawn("producer")
    org.spawn("reporter")
    # Only the producer needs the sandbox; the reporter just consumes the result.
    org.give_tools("producer", [python_tool(Sandbox(SandboxLimits(timeout_sec=10)))])

    producer = Task(description="compute 6 times 7", id="p", target="producer")
    reporter = Task(
        description="report the product", id="r", target="reporter", depends_on=["p"]
    )
    org._tasks = [producer, reporter]

    async def reply(messages):
        text = messages[-1].content
        # producer's second turn: a tool result is present -> finalize.
        if any(m.role == "tool" for m in messages):
            out = [m for m in messages if m.role == "tool"][-1].content
            num = out.split("--- stdout ---")[-1].strip()
            return f"product={num}"
        # reporter: its prompt carries the producer's result.
        if "Results from prerequisite tasks:" in text:
            return f"final answer contains: {text}"
        # producer's first turn: run the real computation.
        return [ToolCall(id="c", name="run_python",
                         arguments={"code": "print(6 * 7)"})]

    result = await org.arun_dag(brain=AsyncMockBrain(reply_fn=reply))
    assert result.succeeded == 2
    assert producer.result == "product=42"          # sandbox really computed it
    assert "product=42" in reporter.result          # passed downstream
