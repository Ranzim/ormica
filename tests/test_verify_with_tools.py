"""The verify/grounding stage must also run in act_with_tools (tool-using agents)."""
import pytest

from ormica import Agent, AsyncAgent
from ormica.arbor import Tree
from ormica.brain import AsyncMockBrain, MockBrain, ToolCall, tool
from ormica.cortex import Constitution, VerificationFailed, must_be_json, verifier


@tool
def fetch() -> str:
    """Fetch something."""
    return "raw data"


def _agent(brain, rules):
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    return Agent(node, brain, constitution=Constitution(rules))


def test_tool_loop_final_response_is_verified_pass():
    # think→tool→think(final, valid JSON) — verify passes, no extra turns.
    brain = MockBrain(replies=[
        [ToolCall(id="t1", name="fetch", arguments={})],
        '{"ok": true}',
    ])
    agent = _agent(brain, [must_be_json()])
    resp = agent.act_with_tools("go", tools=[fetch])
    assert resp.content == '{"ok": true}'


def test_tool_loop_verify_fails_then_model_revises():
    # final answer is not JSON → verify fails → feedback → model corrects.
    brain = MockBrain(replies=[
        [ToolCall(id="t1", name="fetch", arguments={})],
        "not json",          # first final answer: fails verify
        '{"fixed": 1}',      # after feedback: valid
    ])
    agent = _agent(brain, [must_be_json()])
    resp = agent.act_with_tools("go", tools=[fetch])
    assert resp.content == '{"fixed": 1}'
    # the correction note was fed back into the history the brain saw
    last_history = brain.calls[-1]
    assert any("failed verification" in m.content for m in last_history)


def test_tool_loop_verify_gives_up_after_attempts():
    brain = MockBrain(reply_fn=lambda msgs: "never json")
    agent = _agent(brain, [must_be_json()])
    with pytest.raises(VerificationFailed):
        agent.act_with_tools("go", tools=[fetch], max_verify_attempts=2)
    assert agent.node.state.name == "FAILED"


def test_tool_loop_no_verify_rules_is_unchanged():
    brain = MockBrain(replies=[
        [ToolCall(id="t1", name="fetch", arguments={})],
        "plain answer",
    ])
    agent = _agent(brain, [])
    assert agent.act_with_tools("go", tools=[fetch]).content == "plain answer"


def test_tool_loop_grounding_verifier_runs():
    # a custom verifier (the "grounding" pattern) gates the tool-loop answer.
    seen = {}

    def check(ctx):
        seen["v"] = seen.get("v", 0) + 1
        return "42" in ctx["response"].content

    brain = MockBrain(replies=[
        [ToolCall(id="t1", name="fetch", arguments={})],
        "the answer is 41",   # wrong
        "the answer is 42",   # corrected
    ])
    agent = _agent(brain, [verifier("has_42", check)])
    resp = agent.act_with_tools("compute", tools=[fetch])
    assert resp.content == "the answer is 42"
    assert seen["v"] == 2  # verified twice (fail then pass)


@pytest.mark.asyncio
async def test_async_tool_loop_verify_retries():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    brain = AsyncMockBrain(replies=[
        [ToolCall(id="t1", name="fetch", arguments={})],
        "nope",
        "{}",
    ])
    agent = AsyncAgent(node, brain, constitution=Constitution([must_be_json()]))
    resp = await agent.act_with_tools("go", tools=[fetch])
    assert resp.content == "{}"
