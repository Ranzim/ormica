"""The Node — a single agent in the tree."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Optional
from uuid import uuid4


class NodeState(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    DONE = "done"
    FAILED = "failed"
    PRUNED = "pruned"


def _new_id() -> str:
    return uuid4().hex[:12]


def _json_safe(meta: dict) -> dict:
    """Keep only the entries of ``meta`` that survive a JSON round-trip.

    A node's ``meta`` is free-form and may hold runtime objects (live signal
    handles, callables, etc.) that can't be persisted. We keep the scalar/
    structural annotations (risk levels, counts, flags) and silently drop the
    rest so a snapshot works on any backend, JSON-encoded or not.
    """
    safe: dict = {}
    for key, value in meta.items():
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            continue
        safe[key] = value
    return safe


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

    # --- persistence -----------------------------------------------------

    def to_record(self) -> dict[str, Any]:
        """Serialize identity, lineage, state, and JSON-safe ``meta``.

        Lineage is captured as ``parent_id`` (not the object) so a flat list of
        records can rebuild the whole tree. Per-node ``rules`` are *not*
        persisted — they may hold live callables and are re-attached from
        config on load, the same way runtime policy and observers are re-wired.
        """
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "task": self.task,
            "parent_id": self.parent.id if self.parent is not None else None,
            "state": self.state.value,
            "meta": _json_safe(self.meta),
        }

    @classmethod
    def from_record(cls, rec: dict) -> "Node":
        """Reconstruct a bare Node (without lineage) from a record.

        The caller relinks ``parent`` / ``children`` by id; see
        :meth:`Tree.restore`.
        """
        return cls(
            name=rec["name"],
            role=rec.get("role", ""),
            task=rec.get("task", ""),
            id=rec["id"],
            state=NodeState(rec.get("state", "idle")),
            meta=dict(rec.get("meta", {})),
        )
