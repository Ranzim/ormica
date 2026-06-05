"""Canopy — the permission chain, implemented as an arbor SpawnPolicy."""
from __future__ import annotations

from typing import Optional

from ormica.arbor import Node

from .approver import Approver, AutoApprover
from .risk import RiskAssessor, RiskLevel, SpawnRequest, StaticRisk


class Canopy:
    """The permission chain that controls how the tree grows.

    Risk decides routing:

    - ``AUTO``  — parent decides alone; allowed without an approver call.
    - ``CHAIN`` — rises ``chain_levels`` ancestors starting at the parent;
      each ancestor is asked, the first denial short-circuits.
    - ``ROOT``  — walks to the root node; ``root_approver`` decides alone.

    Implements arbor's ``SpawnPolicy`` protocol — drop directly into
    ``Tree(policy=Canopy(...))``.
    """

    def __init__(
        self,
        *,
        assessor: Optional[RiskAssessor] = None,
        chain_approver: Optional[Approver] = None,
        root_approver: Optional[Approver] = None,
        chain_levels: int = 2,
    ) -> None:
        if chain_levels < 1:
            raise ValueError("chain_levels must be >= 1")
        self.assessor: RiskAssessor = assessor or StaticRisk(RiskLevel.AUTO)
        self.chain_approver: Approver = chain_approver or AutoApprover()
        self.root_approver: Approver = root_approver or AutoApprover()
        self.chain_levels = chain_levels

    def allow(self, parent: Node, child_name: str) -> bool:
        risk = self.assessor.assess(parent, child_name)
        request = SpawnRequest(parent=parent, child_name=child_name, risk=risk)

        if risk is RiskLevel.AUTO:
            return True

        if risk is RiskLevel.CHAIN:
            for ancestor in _chain(parent, self.chain_levels):
                if not self.chain_approver.approve(request, ancestor):
                    return False
            return True

        if risk is RiskLevel.ROOT:
            return self.root_approver.approve(request, _root_of(parent))

        raise ValueError(f"unknown risk level: {risk!r}")


def _chain(node: Node, count: int) -> list[Node]:
    chain: list[Node] = []
    current: Optional[Node] = node
    while current is not None and len(chain) < count:
        chain.append(current)
        current = current.parent
    return chain


def _root_of(node: Node) -> Node:
    current = node
    while current.parent is not None:
        current = current.parent
    return current
