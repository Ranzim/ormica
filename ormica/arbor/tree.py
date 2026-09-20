"""The Tree (arbor) — container, growth rules, and traversal."""
from __future__ import annotations

from typing import Callable, Iterator, Optional

from .branch import Branch
from .exceptions import ArborError, MaxDepthExceeded, NodeNotFound, SpawnDenied
from .node import Node, NodeState
from .policy import AllowAllPolicy, SpawnPolicy


class Tree:
    """A living tree of agent nodes.

    Holds the root, indexes every node by id, enforces ``max_depth``,
    and routes spawn requests through a :class:`SpawnPolicy` so canopy
    can later inject the permission chain without arbor changing.
    """

    def __init__(
        self,
        root_name: str,
        owner: str = "",
        *,
        max_depth: int = 8,
        policy: Optional[SpawnPolicy] = None,
        on_spawn: Optional[Callable[[Node], None]] = None,
        on_prune: Optional[Callable[[Node, int], None]] = None,
    ) -> None:
        self.max_depth = max_depth
        self.policy: SpawnPolicy = policy or AllowAllPolicy()
        self.owner = owner
        self.root = Node(name=root_name, role="root")
        self._index: dict[str, Node] = {self.root.id: self.root}
        # Optional observation hooks. Plain callables so arbor takes no
        # dependency on observe; Ormica wires these to its EventBus. A hook
        # that raises must never break tree growth — calls are swallowed.
        self.on_spawn = on_spawn
        self.on_prune = on_prune

    def spawn(
        self,
        parent: Node,
        name: str,
        *,
        role: str = "",
        task: str = "",
    ) -> Node:
        if parent.id not in self._index:
            raise NodeNotFound(f"parent {parent.id!r} is not part of this tree")
        if parent.depth + 1 > self.max_depth:
            raise MaxDepthExceeded(
                f"spawning under {parent.name!r} would exceed max_depth={self.max_depth}"
            )
        if not self.policy.allow(parent, name, role=role, task=task):
            raise SpawnDenied(f"policy denied spawn of {name!r} under {parent.name!r}")

        child = Node(name=name, role=role, task=task, parent=parent)
        parent.children.append(child)
        self._index[child.id] = child
        if self.on_spawn is not None:
            try:
                self.on_spawn(child)
            except Exception:  # noqa: BLE001 — observation must not break growth
                pass
        return child

    def prune(self, node: Node) -> int:
        """Remove a node and its subtree. Returns the number of nodes removed."""
        if node.is_root:
            raise ArborError("cannot prune the root")
        if node.id not in self._index:
            raise NodeNotFound(f"node {node.id!r} is not part of this tree")

        removed = 0
        for descendant in list(node.walk()):
            descendant.state = NodeState.PRUNED
            self._index.pop(descendant.id, None)
            removed += 1

        parent = node.parent
        if parent is not None:
            parent.children = [c for c in parent.children if c.id != node.id]
        node.parent = None
        if self.on_prune is not None:
            try:
                self.on_prune(node, removed)
            except Exception:  # noqa: BLE001 — observation must not break pruning
                pass
        return removed

    def get(self, node_id: str) -> Node:
        try:
            return self._index[node_id]
        except KeyError as exc:
            raise NodeNotFound(node_id) from exc

    def branch(self, node: Node) -> Branch:
        if node.id not in self._index:
            raise NodeNotFound(f"node {node.id!r} is not part of this tree")
        return Branch(node)

    def walk(self) -> Iterator[Node]:
        yield from self.root.walk()

    # --- persistence ---------------------------------------------------------

    def snapshot(self) -> dict:
        """Serialize the whole tree to one JSON-safe record.

        Captures the tree-level settings (``owner``, ``max_depth``) plus a flat
        list of node records in depth-first order (root first). Policy, hooks,
        and per-node rules are runtime wiring, not structure — they are re-
        supplied when the tree is reconstructed, not persisted here.
        """
        return {
            "root_name": self.root.name,
            "owner": self.owner,
            "max_depth": self.max_depth,
            "nodes": [n.to_record() for n in self.walk()],
        }

    def restore(self, snapshot: dict) -> None:
        """Rebuild this tree's nodes and edges from :meth:`snapshot` output.

        Replaces the current root/index in place, preserving the live ``policy``
        and observation hooks already wired on this tree. Spawn/prune hooks do
        *not* fire during restore — reloading a colony is not new growth.
        Raises :class:`ArborError` if the records contain no root or a broken
        parent reference.
        """
        self.owner = snapshot.get("owner", self.owner)
        self.max_depth = snapshot.get("max_depth", self.max_depth)

        nodes: dict[str, Node] = {}
        root: Optional[Node] = None
        for rec in snapshot["nodes"]:
            node = Node.from_record(rec)
            nodes[node.id] = node
            if rec.get("parent_id") is None:
                if root is not None:
                    raise ArborError("snapshot has more than one root node")
                root = node

        if root is None:
            raise ArborError("snapshot has no root node")

        for rec in snapshot["nodes"]:
            parent_id = rec.get("parent_id")
            if parent_id is None:
                continue
            parent = nodes.get(parent_id)
            if parent is None:
                raise ArborError(
                    f"node {rec['id']!r} references missing parent {parent_id!r}"
                )
            child = nodes[rec["id"]]
            child.parent = parent
            parent.children.append(child)

        self.root = root
        self._index = nodes

    def __len__(self) -> int:
        return len(self._index)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Node):
            return item.id in self._index
        if isinstance(item, str):
            return item in self._index
        return False
