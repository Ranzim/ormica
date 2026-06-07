"""The Node — a single agent in the tree."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator, Optional
from uuid import uuid4


class NodeState(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    DONE = "done"
    FAILED = "failed"
    PRUNED = "pruned"


def _new_id() -> str:
    return uuid4().hex[:12]


@dataclass
class Node:
    """A single agent in the arbor.

    Nodes carry identity, lineage (parent / children), a state, a task,
    and a free-form ``meta`` dict for module-specific annotations
    (canopy risk levels, stigma signal strengths, etc.).
    """

    name: str
    role: str = ""
    task: str = ""
    id: str = field(default_factory=_new_id)
    parent: Optional["Node"] = field(default=None, repr=False, compare=False)
    children: list["Node"] = field(default_factory=list, repr=False, compare=False)
    state: NodeState = NodeState.IDLE
    meta: dict = field(default_factory=dict, repr=False, compare=False)
    # Per-node Constitution rules. These cascade down: a rule attached to this
    # node applies to every think / spawn under this node's subtree. Rules
    # attached to the root behave like an org-wide Constitution. List is
    # untyped to avoid a circular dependency on cortex.Rule.
    rules: list = field(default_factory=list, repr=False, compare=False)

    @property
    def depth(self) -> int:
        """Distance from the root. Root nodes have depth 0."""
        d, n = 0, self
        while n.parent is not None:
            d += 1
            n = n.parent
        return d

    @property
    def is_root(self) -> bool:
        return self.parent is None

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def path(self) -> list["Node"]:
        """Chain of nodes from root down to (and including) this node."""
        chain: list[Node] = []
        n: Optional[Node] = self
        while n is not None:
            chain.append(n)
            n = n.parent
        return list(reversed(chain))

    def walk(self) -> Iterator["Node"]:
        """Depth-first traversal yielding this node and every descendant."""
        yield self
        for child in self.children:
            yield from child.walk()
