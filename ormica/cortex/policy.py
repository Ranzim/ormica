"""ConstitutionPolicy — a SpawnPolicy backed by a Constitution.

Lets the same rules govern tree growth (canopy's domain) and runtime actions
(agent's domain) without duplicating the ruleset.
"""
from __future__ import annotations

from typing import Optional

from ormica.arbor import Node, SpawnPolicy

from .constitution import Constitution


class ConstitutionPolicy:
    """An arbor :class:`SpawnPolicy` that consults a :class:`Constitution`.

    A spawn is permitted when no hard rule with ``stage="spawn"`` fails.
    Composes with canopy by wrapping its policy: if ``inner`` is provided,
    both must say yes.
    """

    def __init__(
        self,
        constitution: Constitution,
        *,
        inner: Optional[SpawnPolicy] = None,
    ) -> None:
        self.constitution = constitution
        self.inner = inner

    def allow(self, parent: Node, child_name: str) -> bool:
        context = {
            "parent": parent,
            "child_name": child_name,
            "depth": parent.depth + 1,
        }
        violations = self.constitution.check(context, stage="spawn")
        if any(v.rule.severity == "hard" for v in violations):
            return False
        if self.inner is not None:
            return self.inner.allow(parent, child_name)
        return True
