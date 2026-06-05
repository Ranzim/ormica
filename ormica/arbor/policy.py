"""SpawnPolicy — the seam where canopy plugs in.

Arbor never decides on its own whether a spawn is allowed; it asks a
SpawnPolicy. The default ``AllowAllPolicy`` permits every request so
arbor is usable in isolation. Canopy will provide a real implementation
that walks the permission chain up to the root owner.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .node import Node


@runtime_checkable
class SpawnPolicy(Protocol):
    def allow(self, parent: Node, child_name: str) -> bool: ...


class AllowAllPolicy:
    """Permits every spawn. Used until canopy is wired in."""

    def allow(self, parent: Node, child_name: str) -> bool:  # noqa: ARG002
        return True
