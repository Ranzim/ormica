"""Tests for the top-level Ormica facade."""
import pytest

from ormica import Ormica
from ormica.arbor import Node, NodeNotFound, SpawnDenied
from ormica.canopy import Canopy, DenyApprover, RiskLevel, RoleRisk
from ormica.mycelium import Mycelium


def test_facade_creates_tree_memory_and_signals():
    org = Ormica("Acme", owner="Founder")
    assert org.name == "Acme"
    assert org.owner == "Founder"
    assert org.root.is_root
    assert len(org) == 1
    assert org.memory is not None
    assert org.signals is not None


def test_spawn_defaults_parent_to_root():
    org = Ormica("Acme")
    child = org.spawn("ops")
    assert child.parent is org.root
    assert child.depth == 1


def test_spawn_accepts_node_or_name_as_parent():
    org = Ormica("Acme")
    ops = org.spawn("ops")
    by_node = org.spawn("sales", under=ops)
    by_name = org.spawn("scout", under="ops")

    assert by_node.parent is ops
    assert by_name.parent is ops


def test_find_returns_first_match_and_raises_for_missing():
    org = Ormica("Acme")
    ops = org.spawn("ops")
    assert org.find("ops") is ops

    with pytest.raises(NodeNotFound):
        org.find("ghost")


def test_find_all_returns_every_match():
    org = Ormica("Acme")
    org.spawn("scout")
    a = org.spawn("ops")
    org.spawn("scout", under=a)

    matches = org.find_all("scout")
    assert len(matches) == 2


def test_prune_accepts_node_or_name():
    org = Ormica("Acme")
    org.spawn("ops")
    org.spawn("sales")

    removed = org.prune("ops")
    assert removed == 1
    assert len(org) == 2  # root + sales


def test_write_defaults_author_to_root():
    org = Ormica("Acme")
    entry = org.write("rule", "no overtime")
    assert entry.author == org.root.id

    fetched = org.read("rule")
    assert fetched.value == "no overtime"


def test_write_with_explicit_node_uses_its_id():
    org = Ormica("Acme")
    ops = org.spawn("ops")
    entry = org.write("note", "x", by=ops)
    assert entry.author == ops.id


def test_remember_returns_value_or_default():
    org = Ormica("Acme")
    org.write("k", "v")
    assert org.remember("k") == "v"
    assert org.remember("missing", default=42) == 42


def test_scope_returns_per_node_view():
    org = Ormica("Acme")
    scout = org.spawn("scout")
    view = org.scope(scout)
    view.write("sighting", "northeast")

    entry = org.read("sighting")
    assert entry.author == scout.id


def test_emit_defaults_by_to_root():
    org = Ormica("Acme")
    sig = org.emit("hot_lead", strength=2.0)
    assert sig.sources == {org.root.id}
    assert sig.strength == 2.0


def test_emit_with_node_records_node_as_source():
    org = Ormica("Acme")
    scout = org.spawn("scout")
    sig = org.emit("food", by=scout)
    assert sig.sources == {scout.id}


def test_reinforce_accumulates_via_facade():
    org = Ormica("Acme")
    a = org.spawn("a")
    b = org.spawn("b")
    org.emit("trail", strength=1.0, by=a)
    org.reinforce("trail", amount=1.0, by=b)

    sensed = org.sense("trail")
    assert sensed.strength == pytest.approx(2.0)
    assert sensed.sources == {a.id, b.id}


def test_top_signals_returns_strongest():
    org = Ormica("Acme")
    org.emit("low", strength=0.5)
    org.emit("hi", strength=5.0)
    top1 = org.top_signals(1)
    assert top1[0].topic == "hi"


def test_iteration_walks_tree_in_dfs_order():
    org = Ormica("HQ")
    a = org.spawn("a")
    org.spawn("a1", under=a)
    org.spawn("b")

    names = [n.name for n in org]
    assert names == ["HQ", "a", "a1", "b"]


def test_contains_accepts_node_and_id():
    org = Ormica("Acme")
    scout = org.spawn("scout")
    assert scout in org
    assert scout.id in org
    assert Node(name="ghost") not in org


def test_canopy_policy_is_enforced_through_facade():
    canopy = Canopy(
        assessor=RoleRisk({"finance": RiskLevel.ROOT}),
        root_approver=DenyApprover(),
    )
    org = Ormica("Acme", owner="Founder", policy=canopy)
    org.spawn("scout")  # AUTO — fine

    with pytest.raises(SpawnDenied):
        org.spawn("finance")  # ROOT — denied


def test_external_mycelium_can_be_injected():
    mem = Mycelium()
    org = Ormica("Acme", memory=mem)
    org.write("k", "v")
    # Signals also write to the same store.
    org.emit("hello", strength=1.0)

    assert org.memory is mem
    assert mem.read("k") is not None
    assert mem.read("stigma/hello") is not None


def test_repr_includes_name_owner_and_size():
    org = Ormica("Acme", owner="Founder")
    org.spawn("a")
    text = repr(org)
    assert "Acme" in text
    assert "Founder" in text
    assert "2" in text
