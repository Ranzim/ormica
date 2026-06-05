"""Router — picks a Brain for a given Node."""
from __future__ import annotations

from typing import Optional

from ormica.arbor import Node

from .protocol import Brain


class Router:
    """Resolve a Node to a Brain by name, then role, then default.

    Useful when different agents should use different models — e.g., a
    cheap mock for scouts and a powerful Claude for executive nodes.
    """

    def __init__(
        self,
        default: Brain,
        *,
        by_role: Optional[dict[str, Brain]] = None,
        by_name: Optional[dict[str, Brain]] = None,
    ) -> None:
        self.default = default
        self.by_role: dict[str, Brain] = dict(by_role or {})
        self.by_name: dict[str, Brain] = dict(by_name or {})

    def for_node(self, node: Node) -> Brain:
        if node.name in self.by_name:
            return self.by_name[node.name]
        if node.role and node.role in self.by_role:
            return self.by_role[node.role]
        return self.default
