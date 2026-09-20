"""Recursive delegation — an agent that grows its own sub-colony.

The core promise of an emergent hierarchy is that *an agent facing a task too
big to do alone spawns helpers to do it* — and those helpers can do the same,
recursively, until the work is small enough to finish directly. This wires that
into a single tool.

Give an agent the ``delegate`` tool and, when it decides a task needs breaking
down, it calls ``delegate([subtask, …])``: each subtask spawns a child agent
**under the delegating node**, the child runs it (with its *own* delegate tool
until the depth cap), and the results flow back up. Planner + spawn + run become
one recursive primitive.

Bounded on every axis so it can't run away:

- **depth** — children get a delegate tool only while ``depth + 1 < max_depth``.
- **fan-out** — at most ``max_subtasks`` per call.
- **the colony's own gates** — every spawn goes through the tree's
  :class:`~ormica.arbor.SpawnPolicy` (constitution rules + a
  :class:`~ormica.canopy.BudgetGovernor`), so ``max_agents`` / token ceilings
  still apply; a denied spawn is reported back, not fatal.

    org.solve("Plan and cost the Q3 launch", brain=brain, max_depth=3)
"""
from __future__ import annotations

from typing import Any, Optional

from ormica.brain import Tool


class DelegationBuilder:
    """Builds a per-node ``delegate`` tool that spawns and runs sub-agents."""

    def __init__(
        self,
        org: Any,
        node: Any,
        brain: Any,
        *,
        max_depth: int = 2,
        depth: int = 0,
        max_subtasks: int = 5,
        base_tools: Optional[list] = None,
    ) -> None:
        self.org = org
        self.node = node
        self.brain = brain
        self.max_depth = max_depth
        self.depth = depth
        self.max_subtasks = max_subtasks
        self.base_tools = list(base_tools or [])
        self.spawned = 0

    def _child_tools(self, child_node: Any) -> list:
        """A child gets the base tools, plus its own delegate tool if depth allows."""
        tools = list(self.base_tools)
        if self.depth + 1 < self.max_depth:
            tools.append(
                DelegationBuilder(
                    self.org, child_node, self.brain,
                    max_depth=self.max_depth, depth=self.depth + 1,
                    max_subtasks=self.max_subtasks, base_tools=self.base_tools,
                ).as_tool()
            )
        return tools

    def __call__(self, subtasks: Any) -> str:
        from ormica.agent import Agent

        if isinstance(subtasks, str):
            subtasks = [subtasks]
        if not isinstance(subtasks, list):
            return "refused: subtasks must be a list of strings"

        results: list[str] = []
        for i, raw in enumerate(subtasks[: self.max_subtasks], start=1):
            desc = str(raw).strip()
            if not desc:
                continue
            try:
                child = self.org.tree.spawn(
                    self.node,
                    f"{self.node.name}.sub{self.spawned + 1}",
                    role="delegate",
                    task=desc,
                )
            except Exception as exc:  # noqa: BLE001 — governor/depth denial, not fatal
                results.append(f"[{i}] '{desc[:40]}' not spawned: {type(exc).__name__}")
                continue
            self.spawned += 1

            agent = Agent(
                child, self.brain,
                memory=self.org.memory, signals=self.org.signals,
                constitution=self.org.constitution,
            )
            agent.events = self.org.events
            try:
                tools = self._child_tools(child)
                resp = (
                    agent.act_with_tools(desc, tools=tools)
                    if tools else agent.act(desc)
                )
                results.append(f"[{desc[:48]}] → {resp.content}")
            except Exception as exc:  # noqa: BLE001 — a failed child ≠ a dead parent
                results.append(f"[{desc[:48]}] failed: {type(exc).__name__}: {exc}")

        if not results:
            return "no subtasks delegated"
        return "delegated results:\n" + "\n".join(results)

    def as_tool(self) -> Tool:
        return Tool(
            name="delegate",
            description=(
                "Break your task into concrete subtasks and delegate each to a "
                "sub-agent you spawn. Use this when the task is too complex to do "
                "alone — each sub-agent runs and returns its result, which you then "
                f"synthesise. At most {self.max_subtasks} subtasks per call."
            ),
            fn=self,
            schema={
                "type": "object",
                "properties": {
                    "subtasks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "concrete subtask descriptions to delegate",
                    }
                },
                "required": ["subtasks"],
            },
        )
