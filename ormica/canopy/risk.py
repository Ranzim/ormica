"""Risk levels and assessors — how canopy classifies a spawn request."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from ormica.arbor import Node


class RiskLevel(str, Enum):
    AUTO = "auto"    # parent decides alone; always allowed
    CHAIN = "chain"  # rises up ``chain_levels`` ancestors; each must approve
    ROOT = "root"    # only the root owner can approve


@dataclass(frozen=True)
class SpawnRequest:
    parent: Node
    child_name: str
    risk: RiskLevel


@runtime_checkable
class RiskAssessor(Protocol):
    def assess(self, parent: Node, child_name: str) -> RiskLevel: ...


class StaticRisk:
    """Returns the same risk level for every request."""

    def __init__(self, level: RiskLevel = RiskLevel.AUTO) -> None:
        self.level = level

    def assess(self, parent: Node, child_name: str) -> RiskLevel:  # noqa: ARG002
        return self.level


class RoleRisk:
    """Look up risk by child name (a role label), falling back to ``default``.

    Example::

        RoleRisk({"finance": RiskLevel.ROOT, "scout": RiskLevel.AUTO})
    """

    def __init__(
        self,
        by_name: dict[str, RiskLevel],
        default: RiskLevel = RiskLevel.AUTO,
    ) -> None:
        self.by_name = dict(by_name)
        self.default = default

    def assess(self, parent: Node, child_name: str) -> RiskLevel:  # noqa: ARG002
        return self.by_name.get(child_name, self.default)
