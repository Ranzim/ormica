"""Human-in-the-loop gates for tool actions.

Canopy already gates *spawns* behind approval (the AUTO/CHAIN/ROOT chain). This
module gates *actions* — the tool calls an agent makes. Wrap a high-risk tool
(issue a refund, send an email, run a command, open a PR) so a human must
approve the specific call before it executes.

The gate is **fail-closed**: a denial — or an approver that errors — returns a
refusal string the model reads, and the underlying tool never runs. Approvals
are requested only for calls that matter, via an optional ``when`` predicate on
the arguments, so routine calls aren't interrupted.

    from ormica.approval import require_approval, ConsoleActionApprover

    safe_refund = require_approval(
        issue_refund,
        ConsoleActionApprover(),
        when=lambda args: args.get("amount", 0) > 1000,   # only large refunds
    )
    agent.act_with_tools("Refund order 123", tools=[safe_refund])

Approvers mirror canopy's: :class:`AutoApproveActions`, :class:`DenyActions`,
:class:`ConsoleActionApprover`, and :class:`CallbackActionApprover` (the seam
for Slack / a web UI / a queue).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import IO, Any, Callable, Optional, Protocol, runtime_checkable

from ormica.brain import Tool


@dataclass
class ActionRequest:
    """A pending tool call awaiting approval."""

    tool_name: str
    arguments: dict = field(default_factory=dict)
    task_id: str = ""

    def summary(self) -> str:
        args = ", ".join(f"{k}={v!r}" for k, v in self.arguments.items())
        return f"{self.tool_name}({args})"


@runtime_checkable
class ActionApprover(Protocol):
    """Decides whether a specific tool call may run."""

    def approve(self, request: ActionRequest) -> bool: ...


class AutoApproveActions:
    """Always approves. Harmless default / for turning a gate off in tests."""

    def approve(self, request: ActionRequest) -> bool:  # noqa: ARG002
        return True


class DenyActions:
    """Always denies. Lockdown mode."""

    def approve(self, request: ActionRequest) -> bool:  # noqa: ARG002
        return False


class ConsoleActionApprover:
    """Interactive terminal approver — prompts the operator y/N per action.

    Anything starting with ``y``/``Y`` approves; everything else (including an
    empty line / EOF) denies. **Not for production** — blocks until input.
    """

    def __init__(
        self,
        input_stream: Optional[IO] = None,
        output_stream: Optional[IO] = None,
    ) -> None:
        self.input_stream = input_stream if input_stream is not None else sys.stdin
        self.output_stream = (
            output_stream if output_stream is not None else sys.stdout
        )

    def approve(self, request: ActionRequest) -> bool:
        self.output_stream.write(f"approve action {request.summary()}? [y/N]: ")
        self.output_stream.flush()
        answer = self.input_stream.readline().strip().lower()
        return answer.startswith("y")


class CallbackActionApprover:
    """Delegate the decision to a Python callable — the custom-integration seam.

    The callable receives the :class:`ActionRequest` and returns ``bool``
    (e.g. post to Slack and block on a button press, or POST to a web UI).
    """

    def __init__(self, callback: Callable[[ActionRequest], bool]) -> None:
        self.callback = callback

    def approve(self, request: ActionRequest) -> bool:
        return bool(self.callback(request))


def require_approval(
    tool: Tool,
    approver: ActionApprover,
    *,
    when: Optional[Callable[[dict], bool]] = None,
    task_id: str = "",
) -> Tool:
    """Wrap ``tool`` so a human must approve a call before it runs.

    ``when`` (optional) receives the call's arguments and returns ``True`` if
    that specific call needs approval; when it returns ``False`` the tool runs
    directly. With no ``when``, every call is gated.

    Denials, and any error raised by the approver, return a refusal string and
    do **not** run the tool (fail-closed). The wrapped tool keeps the original
    name, description (with a note), and schema.
    """

    def gated(**kwargs: Any) -> Any:
        if when is None or when(kwargs):
            request = ActionRequest(
                tool_name=tool.name, arguments=dict(kwargs), task_id=task_id
            )
            try:
                approved = approver.approve(request)
            except Exception as exc:  # noqa: BLE001 - fail closed, tell the model
                return (
                    f"refused: approval check for {tool.name!r} failed "
                    f"({type(exc).__name__}: {exc}); action not performed"
                )
            if not approved:
                return (
                    f"refused: a human reviewer denied {tool.name!r}; "
                    "action not performed"
                )
        return tool.fn(**kwargs)

    return Tool(
        name=tool.name,
        description=tool.description + " (requires human approval before it runs)",
        fn=gated,
        schema=tool.schema,
    )


def gate_tools(
    tools: list[Tool],
    approver: ActionApprover,
    *,
    when: Optional[Callable[[dict], bool]] = None,
) -> list[Tool]:
    """Apply :func:`require_approval` to every tool in a list."""
    return [require_approval(t, approver, when=when) for t in tools]
