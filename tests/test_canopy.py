"""Tests for the canopy module — risk, approvers, and the permission chain."""
from dataclasses import dataclass, field

import pytest

from ormica.arbor import Node, SpawnDenied, Tree
from ormica.canopy import (
    Approver,
    AutoApprover,
    Canopy,
    DenyApprover,
    RiskAssessor,
    RiskLevel,
    RoleRisk,
    SpawnRequest,
    StaticRisk,
)


@dataclass
class RecordingApprover:
    """Records every approval question and returns ``answer`` each time."""

    answer: bool = True
    calls: list[tuple[SpawnRequest, Node]] = field(default_factory=list)

    def approve(self, request: SpawnRequest, at: Node) -> bool:
        self.calls.append((request, at))
        return self.answer


def test_static_risk_returns_fixed_level():
    assessor = StaticRisk(RiskLevel.ROOT)
    assert assessor.assess(Node(name="p"), "anything") is RiskLevel.ROOT


def test_role_risk_falls_back_to_default():
    assessor = RoleRisk({"finance": RiskLevel.ROOT}, default=RiskLevel.AUTO)
    assert assessor.assess(Node(name="p"), "finance") is RiskLevel.ROOT
    assert assessor.assess(Node(name="p"), "scout") is RiskLevel.AUTO


def test_protocols_recognise_default_implementations():
    assert isinstance(StaticRisk(), RiskAssessor)
    assert isinstance(AutoApprover(), Approver)
    assert isinstance(DenyApprover(), Approver)


def test_auto_risk_always_allowed_without_calling_approver():
    rec = RecordingApprover(answer=False)
    canopy = Canopy(chain_approver=rec, root_approver=rec)

    assert canopy.allow(Node(name="p"), "child") is True
    assert rec.calls == []  # AUTO never consults an approver


def test_chain_consults_each_ancestor_and_short_circuits_on_denial():
    tree = Tree("HQ")
    dept = tree.spawn(tree.root, "dept")
    manager = tree.spawn(dept, "manager")

    rec = RecordingApprover(answer=False)
    canopy = Canopy(
        assessor=StaticRisk(RiskLevel.CHAIN),
        chain_approver=rec,
        chain_levels=3,
    )

    assert canopy.allow(manager, "report") is False
    # First denial short-circuits the rest of the chain.
    assert len(rec.calls) == 1
    asked = rec.calls[0][1]
    assert asked is manager


def test_chain_requires_every_ancestor_to_approve():
    tree = Tree("HQ")
    dept = tree.spawn(tree.root, "dept")
    manager = tree.spawn(dept, "manager")

    rec = RecordingApprover(answer=True)
    canopy = Canopy(
        assessor=StaticRisk(RiskLevel.CHAIN),
        chain_approver=rec,
        chain_levels=2,
    )

    assert canopy.allow(manager, "report") is True
    consulted = [node for _, node in rec.calls]
    assert consulted == [manager, dept]  # walks up exactly chain_levels


def test_chain_walks_no_further_than_root():
    tree = Tree("HQ")
    a = tree.spawn(tree.root, "a")  # depth 1
    rec = RecordingApprover(answer=True)
    canopy = Canopy(
        assessor=StaticRisk(RiskLevel.CHAIN),
        chain_approver=rec,
        chain_levels=10,
    )

    assert canopy.allow(a, "child") is True
    # Only ``a`` and root exist — chain stops at root despite chain_levels=10.
    consulted = [node for _, node in rec.calls]
    assert [n.name for n in consulted] == ["a", "HQ"]


def test_root_risk_asks_root_only():
    tree = Tree("HQ")
    dept = tree.spawn(tree.root, "dept")
    manager = tree.spawn(dept, "manager")

    rec = RecordingApprover(answer=True)
    canopy = Canopy(assessor=StaticRisk(RiskLevel.ROOT), root_approver=rec)

    assert canopy.allow(manager, "ceo") is True
    assert len(rec.calls) == 1
    assert rec.calls[0][1] is tree.root


def test_root_denial_blocks_spawn():
    tree = Tree("HQ")
    canopy = Canopy(
        assessor=StaticRisk(RiskLevel.ROOT),
        root_approver=DenyApprover(),
    )
    assert canopy.allow(tree.root, "anything") is False


def test_canopy_drops_into_tree_as_spawn_policy():
    """End-to-end: configuring a Tree with Canopy actually blocks spawns."""
    canopy = Canopy(
        assessor=RoleRisk({"finance": RiskLevel.ROOT}),
        root_approver=DenyApprover(),
    )
    tree = Tree("HQ", policy=canopy)

    # AUTO-risk spawn passes.
    tree.spawn(tree.root, "scout")

    # ROOT-risk spawn is denied by the root approver and arbor raises.
    with pytest.raises(SpawnDenied):
        tree.spawn(tree.root, "finance")


def test_invalid_chain_levels_rejected():
    with pytest.raises(ValueError):
        Canopy(chain_levels=0)
