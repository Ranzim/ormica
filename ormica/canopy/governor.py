"""BudgetGovernor — hard economic ceilings on colony growth.

Canopy's permission chain (:class:`Canopy`) answers *"who must approve this
spawn?"*. The governor answers a different, blunter question: *"can the colony
afford another agent at all?"* — the ceiling that stops a self-spawning colony
from exploding in agent count or burning through a token budget.

It's an arbor :class:`~ormica.arbor.SpawnPolicy`, so it plugs into the same
seam every other spawn control uses, and composes with them via ``inner``
(both must say yes). Three independent ceilings, any subset active:

- ``max_agents`` — cap the number of *live* nodes in the tree.
- ``max_spawns`` — cap the *cumulative* spawns this governor has approved
  (counts even nodes later pruned — bounds churn, not just size).
- ``budget`` + ``reserve_tokens`` — deny new spawns once a shared
  :class:`~ormica.brain.TokenBudget` is (nearly) spent: don't grow the
  colony when there's no budget left to run the new agent.

Denials return ``False`` (arbor raises ``SpawnDenied``); the reason is stored
on ``last_denial`` for observability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ormica.arbor import Node, SpawnPolicy
from ormica.brain import TokenBudget


@dataclass
class BudgetGovernor:
    """A :class:`SpawnPolicy` enforcing economic ceilings on growth."""

    max_agents: Optional[int] = None
    max_spawns: Optional[int] = None
    budget: Optional[TokenBudget] = None
    reserve_tokens: int = 0
    inner: Optional[SpawnPolicy] = None
    approved: int = field(default=0, init=False)
    last_denial: str = field(default="", init=False)

    def _deny(self, reason: str) -> bool:
        self.last_denial = reason
        return False

    def allow(
        self,
        parent: Node,
        child_name: str,
        *,
        role: str = "",
        task: str = "",
    ) -> bool:
        if self.max_agents is not None:
            root = parent.path()[0]
            live = sum(1 for _ in root.walk())
            if live >= self.max_agents:
                return self._deny(
                    f"max_agents={self.max_agents} reached ({live} live nodes)"
                )
        if self.max_spawns is not None and self.approved >= self.max_spawns:
            return self._deny(f"max_spawns={self.max_spawns} reached")
        if self.budget is not None and self.budget.remaining <= self.reserve_tokens:
            return self._deny(
                f"token budget too low to spawn "
                f"(remaining={self.budget.remaining}, reserve={self.reserve_tokens})"
            )
        if self.inner is not None and not self.inner.allow(
            parent, child_name, role=role, task=task
        ):
            return self._deny("inner policy denied")
        self.approved += 1
        return True
