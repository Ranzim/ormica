"""Tests for persisting the agent tree — snapshot / restore + save_tree / load_tree."""
import json

import pytest

from ormica import Ormica
from ormica.arbor import ArborError, NodeState, Tree
from ormica.arbor.node import Node
from ormica.mycelium import FileBackend, Mycelium


# --- Node record round-trip ---------------------------------------------------


def test_node_record_round_trip():
    root = Node(name="HQ", role="root")
    child = Node(name="scout", role="worker", task="find leads", parent=root)
    child.state = NodeState.WORKING
    child.meta = {"risk": "auto", "spawns": 3}

    rec = child.to_record()
    assert rec["parent_id"] == root.id
    assert rec["state"] == "working"

    rebuilt = Node.from_record(rec)
    assert rebuilt.id == child.id
    assert rebuilt.name == "scout"
    assert rebuilt.role == "worker"
    assert rebuilt.task == "find leads"
    assert rebuilt.state is NodeState.WORKING
    assert rebuilt.meta == {"risk": "auto", "spawns": 3}
    # from_record yields a bare node; the tree relinks lineage.
    assert rebuilt.parent is None and rebuilt.children == []


def test_to_record_drops_unserializable_meta():
    node = Node(name="n")
    node.meta = {"count": 7, "handle": lambda: None, "obj": object()}
    rec = node.to_record()
    assert rec["meta"] == {"count": 7}
    # the whole record must be JSON-encodable
    json.dumps(rec)


def test_rules_are_not_persisted():
    node = Node(name="n")
    node.rules = [object()]  # a non-serializable rule stand-in
    assert "rules" not in node.to_record()


# --- Tree snapshot / restore --------------------------------------------------


def _sample_tree() -> Tree:
    tree = Tree("HQ", owner="Founder", max_depth=5)
    ops = tree.spawn(tree.root, "ops", role="dept")
    tree.spawn(ops, "scout", role="worker", task="scan")
    tree.spawn(ops, "closer", role="worker")
    tree.spawn(tree.root, "sales", role="dept")
    return tree


def test_snapshot_captures_structure_and_settings():
    tree = _sample_tree()
    snap = tree.snapshot()
    assert snap["root_name"] == "HQ"
    assert snap["owner"] == "Founder"
    assert snap["max_depth"] == 5
    assert len(snap["nodes"]) == len(tree) == 5
    # root record first (depth-first, root first)
    assert snap["nodes"][0]["parent_id"] is None


def test_restore_rebuilds_structure():
    original = _sample_tree()
    snap = original.snapshot()

    fresh = Tree("placeholder")
    fresh.restore(snap)

    assert fresh.owner == "Founder"
    assert fresh.max_depth == 5
    assert len(fresh) == 5
    assert fresh.root.name == "HQ"

    # every node reachable by id, with lineage intact
    for node in original.walk():
        restored = fresh.get(node.id)
        assert restored.name == node.name
        assert restored.role == node.role
        if node.parent is not None:
            assert restored.parent.id == node.parent.id
    # child count matches under ops
    ops_id = [n for n in original.walk() if n.name == "ops"][0].id
    assert len(fresh.get(ops_id).children) == 2


def test_restore_preserves_policy_and_hooks():
    spawned: list[str] = []
    tree = Tree("HQ", on_spawn=lambda n: spawned.append(n.name))
    ops = tree.spawn(tree.root, "ops")
    assert spawned == ["ops"]
    policy = tree.policy
    snap = tree.snapshot()

    tree.restore(snap)
    # restore is not growth — no spawn hook fired
    assert spawned == ["ops"]
    # policy object is preserved; new spawns still route through it and fire hooks
    assert tree.policy is policy
    tree.spawn(tree.get(ops.id), "scout")
    assert spawned == ["ops", "scout"]


def test_restore_rejects_broken_snapshots():
    with pytest.raises(ArborError):
        Tree("x").restore({"nodes": []})
    with pytest.raises(ArborError):
        Tree("x").restore(
            {"nodes": [{"id": "a", "name": "child", "parent_id": "missing"}]}
        )


# --- Ormica facade: save_tree / load_tree -------------------------------------


def test_load_tree_returns_false_when_nothing_saved():
    org = Ormica("HQ")
    assert org.load_tree() is False


def test_save_and_load_tree_in_process():
    org = Ormica("HQ", owner="Founder")
    ops = org.spawn("ops")
    org.spawn("scout", under=ops)
    org.save_tree()

    # simulate a fresh colony that reloads the persisted structure
    reloaded = Ormica("placeholder", memory=org.memory)
    assert reloaded.load_tree() is True
    assert len(reloaded.tree) == 3
    assert reloaded.root.name == "HQ"
    assert {n.name for n in reloaded} == {"HQ", "ops", "scout"}


def test_tree_survives_a_process_restart(tmp_path):
    db = str(tmp_path / "colony")
    org = Ormica("HQ", owner="Founder", memory_path=db)
    ops = org.spawn("ops", role="dept")
    org.spawn("scout", under=ops, role="worker")
    org.save_tree()

    # brand-new facade + brand-new mycelium reading the same file backend
    revived = Ormica("placeholder", memory=Mycelium(backend=FileBackend(db)))
    assert revived.load_tree() is True
    assert {n.name for n in revived} == {"HQ", "ops", "scout"}
    scout = revived.find("scout")
    assert scout.role == "worker"
    assert scout.parent.name == "ops"
