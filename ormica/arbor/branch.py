"""A Branch — a view over a subtree rooted at a node."""
from __future__ import annotations

from typing import Iterator

from .node import Node


class Branch:
    """A subtree view. Useful for bulk operations on a node and its descendants."""

    def __init__(self, root: Node) -> None:
        self.root = root

    def nodes(self) -> list[Node]:
        return list(self.root.walk())

    def __iter__(self) -> Iterator[Node]:
        return self.root.walk()

    def __len__(self) -> int:
        return sum(1 for _ in self.root.walk())
