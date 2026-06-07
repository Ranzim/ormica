"""The Tree (arbor) — container, growth rules, and traversal."""
from __future__ import annotations

from typing import Iterator, Optional

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
    ) -> None:
        self.max_depth = max_depth
        self.policy: SpawnPolicy = policy or AllowAllPolicy()
        self.owner = owner
        self.root = Node(name=root_name, role="root")
        self._index: dict[str, Node] = {self.root.id: self.root}

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

    def __len__(self) -> int:
        return len(self._index)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Node):
            return item.id in self._index
        if isinstance(item, str):
            return item in self._index
        return False
