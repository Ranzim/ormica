"""Tests for the arbor module — Node, Tree, Branch, SpawnPolicy."""
import pytest

from ormica.arbor import (
    AllowAllPolicy,
    ArborError,
    Branch,
    MaxDepthExceeded,
    Node,
    NodeNotFound,
    NodeState,
    SpawnDenied,
    SpawnPolicy,
    Tree,
)


def test_tree_starts_with_only_root():
    tree = Tree("HQ", owner="Founder")
    assert len(tree) == 1
    assert tree.root.is_root
    assert tree.root.is_leaf
    assert tree.root.depth == 0
    assert tree.owner == "Founder"


def test_spawn_attaches_child_and_indexes_it():
    tree = Tree("HQ")
    child = tree.spawn(tree.root, "scout", role="explorer", task="survey area")

    assert child.parent is tree.root
    assert child in tree.root.children
    assert child.depth == 1
    assert child.id in tree
    assert tree.get(child.id) is child
    assert len(tree) == 2


def test_depth_limit_blocks_excess_spawning():
    tree = Tree("HQ", max_depth=2)
    a = tree.spawn(tree.root, "a")        # depth 1
    b = tree.spawn(a, "b")                # depth 2

    with pytest.raises(MaxDepthExceeded):
        tree.spawn(b, "c")                # depth 3 — denied


def test_spawn_policy_can_deny():
    class DenyPolicy:
        def allow(self, parent: Node, child_name: str) -> bool:
            return child_name != "forbidden"

    tree = Tree("HQ", policy=DenyPolicy())
    tree.spawn(tree.root, "allowed")

    with pytest.raises(SpawnDenied):
        tree.spawn(tree.root, "forbidden")


def test_spawn_with_unknown_parent_raises():
    tree = Tree("HQ")
    orphan = Node(name="orphan")
    with pytest.raises(NodeNotFound):
        tree.spawn(orphan, "child")


def test_prune_removes_subtree_and_marks_state():
    tree = Tree("HQ")
    a = tree.spawn(tree.root, "a")
    b = tree.spawn(a, "b")
    tree.spawn(b, "c")
    tree.spawn(tree.root, "sibling")

    removed = tree.prune(a)

    assert removed == 3
    assert a.state == NodeState.PRUNED
    assert b.state == NodeState.PRUNED
    assert a.id not in tree
    assert b.id not in tree
    assert a not in tree.root.children
    assert len(tree) == 2  # root + sibling


def test_cannot_prune_root():
    tree = Tree("HQ")
    with pytest.raises(ArborError):
        tree.prune(tree.root)


def test_walk_is_depth_first_and_includes_root():
    tree = Tree("HQ")
    a = tree.spawn(tree.root, "a")
    tree.spawn(a, "a1")
    tree.spawn(a, "a2")
    tree.spawn(tree.root, "b")

    names = [n.name for n in tree.walk()]
    assert names == ["HQ", "a", "a1", "a2", "b"]


def test_path_goes_from_root_to_node():
    tree = Tree("HQ")
    a = tree.spawn(tree.root, "a")
    b = tree.spawn(a, "b")

    assert [n.name for n in b.path()] == ["HQ", "a", "b"]


def test_branch_view_iterates_subtree():
    tree = Tree("HQ")
    a = tree.spawn(tree.root, "a")
    tree.spawn(a, "a1")
    tree.spawn(a, "a2")

    branch = tree.branch(a)
    assert isinstance(branch, Branch)
    assert len(branch) == 3
    assert {n.name for n in branch} == {"a", "a1", "a2"}


def test_allow_all_policy_satisfies_protocol():
    policy = AllowAllPolicy()
    assert isinstance(policy, SpawnPolicy)
    assert policy.allow(Node(name="p"), "anything") is True
