"""Approvers — the authority asked when a spawn request rises up the tree."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

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
