"""Approvers — the authority asked when a spawn request rises up the tree."""
from __future__ import annotations

import sys
from typing import IO, Callable, Optional, Protocol, runtime_checkable

from ormica.arbor import Node

from .risk import SpawnRequest


@runtime_checkable
class Approver(Protocol):
    """Decides whether a spawn request is granted at the asked authority.

    ``at`` is the node whose authority is being invoked: each ancestor
    walked during CHAIN, the root for ROOT. A human/CLI approver can use
    ``at.name`` and ``at.depth`` to render the prompt.
    """

    def approve(self, request: SpawnRequest, at: Node) -> bool: ...


class AutoApprover:
    """Always approves. The harmless default until a real approver is wired in."""

    def approve(self, request: SpawnRequest, at: Node) -> bool:  # noqa: ARG002
        return True


class DenyApprover:
    """Always denies. Useful for tests and lockdown modes."""

    def approve(self, request: SpawnRequest, at: Node) -> bool:  # noqa: ARG002
        return False


class ConsoleApprover:
    """Interactive terminal approver — prompts the operator for y/n on each request.

    Reads from ``input_stream`` (default ``sys.stdin``) and writes the prompt
    to ``output_stream`` (default ``sys.stdout``). Anything starting with ``y``
    or ``Y`` is approved; everything else is denied — so an empty line / EOF
    safely defaults to deny.

    Useful for local development of a colony where you want a human in the
    loop for ``ROOT`` or ``CHAIN`` decisions but don't want to wire up a real
    paging system yet. **Not for production** — blocks the spawn until input
    arrives.

    ::

        canopy = Canopy(
            assessor=RoleRisk({"finance": RiskLevel.ROOT}),
            root_approver=ConsoleApprover(),
        )
        org = Ormica("Acme", policy=canopy)
        org.spawn("treasury", role="finance")
        # prompt: "approve spawn 'treasury' (role=finance) under 'Acme'? [y/N]:"
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

    def approve(self, request: SpawnRequest, at: Node) -> bool:
        prompt = (
            f"approve spawn {request.child_name!r} (role={request.parent.role!r}, "
            f"risk={request.risk.value}) under {at.name!r}? [y/N]: "
        )
        self.output_stream.write(prompt)
        self.output_stream.flush()
        answer = self.input_stream.readline().strip().lower()
        return answer.startswith("y")


class CallbackApprover:
    """Delegate the approval decision to a Python callable.

    The seam for any custom human-in-the-loop integration: Slack
    interactive messages, a web UI that POSTs back, a queue worker that
    waits for a moderator. The callable receives the same ``(request, at)``
    pair the Approver protocol gets and must return ``bool``.

    ::

        def slack_approver(request, at):
            ts = post_slack(text=f"approve {request.child_name} under {at.name}?")
            return wait_for_button_press(ts)  # blocks until human clicks

        canopy = Canopy(root_approver=CallbackApprover(slack_approver))

    The default callable is a deny — use a typed import error if you forgot
    to pass one, rather than silently letting everything through.
    """

    def __init__(
        self,
        callback: Callable[[SpawnRequest, Node], bool],
    ) -> None:
        self.callback = callback

    def approve(self, request: SpawnRequest, at: Node) -> bool:
        return bool(self.callback(request, at))
