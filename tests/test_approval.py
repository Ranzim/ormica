"""Tests for human-in-the-loop action gates."""
import io

from ormica import Agent
from ormica.approval import (
    ActionRequest,
    AutoApproveActions,
    CallbackActionApprover,
    ConsoleActionApprover,
    DenyActions,
    gate_tools,
    require_approval,
)
from ormica.arbor import Tree
from ormica.brain import MockBrain, Tool, ToolCall, tool


def _effectful_tool(log: list):
    @tool
    def issue_refund(order_id: str, amount: int) -> str:
        """Issue a refund."""
        log.append((order_id, amount))
        return f"refunded {amount} for {order_id}"

    return issue_refund


# --- approvers ----------------------------------------------------------------


def test_auto_and_deny_approvers():
    req = ActionRequest("t", {"x": 1})
    assert AutoApproveActions().approve(req) is True
    assert DenyActions().approve(req) is False


def test_console_action_approver_yes_no():
    req = ActionRequest("issue_refund", {"amount": 500})
    yes = ConsoleActionApprover(io.StringIO("y\n"), io.StringIO())
    no = ConsoleActionApprover(io.StringIO("\n"), io.StringIO())  # empty -> deny
    assert yes.approve(req) is True
    assert no.approve(req) is False


def test_callback_approver_receives_request():
    seen = {}

    def cb(request: ActionRequest) -> bool:
        seen["name"] = request.tool_name
        seen["args"] = request.arguments
        return request.arguments["amount"] < 1000

    approver = CallbackActionApprover(cb)
    assert approver.approve(ActionRequest("issue_refund", {"amount": 500})) is True
    assert approver.approve(ActionRequest("issue_refund", {"amount": 5000})) is False
    assert seen["name"] == "issue_refund"


# --- require_approval ---------------------------------------------------------


def test_approved_runs_the_tool():
    log: list = []
    gated = require_approval(_effectful_tool(log), AutoApproveActions())
    out = gated(order_id="A1", amount=50)
    assert "refunded 50" in out
    assert log == [("A1", 50)]


def test_denied_blocks_the_tool():
    log: list = []
    gated = require_approval(_effectful_tool(log), DenyActions())
    out = gated(order_id="A1", amount=50)
    assert out.startswith("refused:")
    assert log == []  # side effect never happened


def test_approver_error_fails_closed():
    log: list = []

    class Boom:
        def approve(self, request):
            raise RuntimeError("pager down")

    gated = require_approval(_effectful_tool(log), Boom())
    out = gated(order_id="A1", amount=50)
    assert out.startswith("refused:") and "pager down" in out
    assert log == []


def test_when_predicate_gates_only_risky_calls():
    log: list = []
    calls = {"asked": 0}

    class CountingDeny:
        def approve(self, request):
            calls["asked"] += 1
            return False

    gated = require_approval(
        _effectful_tool(log), CountingDeny(), when=lambda a: a["amount"] > 1000
    )
    # Small refund: not gated, runs directly.
    assert "refunded 10" in gated(order_id="A", amount=10)
    assert calls["asked"] == 0
    assert log == [("A", 10)]
    # Large refund: gated, approver consulted, denied.
    assert gated(order_id="B", amount=5000).startswith("refused:")
    assert calls["asked"] == 1
    assert log == [("A", 10)]  # large one blocked


def test_wrapped_tool_preserves_name_and_schema():
    log: list = []
    original = _effectful_tool(log)
    gated = require_approval(original, AutoApproveActions())
    assert isinstance(gated, Tool)
    assert gated.name == original.name
    assert gated.schema == original.schema
    assert "human approval" in gated.description


def test_gate_tools_wraps_all():
    log: list = []
    tools = gate_tools([_effectful_tool(log)], DenyActions())
    assert len(tools) == 1
    assert tools[0](order_id="x", amount=1).startswith("refused:")


# --- agent integration --------------------------------------------------------


def test_agent_denied_action_records_refusal():
    log: list = []
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "support")
    brain = MockBrain(
        replies=[
            [ToolCall(id="t1", name="issue_refund",
                      arguments={"order_id": "A1", "amount": 9000})],
            "I could not issue the refund; it needs approval.",
        ]
    )
    gated = require_approval(_effectful_tool(log), DenyActions())
    agent = Agent(node, brain)
    resp = agent.act_with_tools("Refund order A1", tools=[gated])
    assert resp.content.startswith("I could not")
    tool_msg = next(m for m in brain.calls[1] if m.role == "tool")
    assert tool_msg.content.startswith("refused:")
    assert log == []  # no refund happened
