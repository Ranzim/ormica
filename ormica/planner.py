"""Planner — decompose a complex goal into an ordered plan of subtasks.

.. note:: **Opt-in — a top-down alternative to emergent growth.** Ormica's core
   model is *emergent*: you define goals and the colony grows its own tree by
   spawning ("no fixed graphs, no predefined chains"). The planner is the
   deliberate *opposite* — explicit, up-front decomposition into a fixed DAG.
   Use it when you want a plan you can **inspect and approve before running**
   (auditability, compliance, cost estimation) rather than trusting emergence.
   It's an optional layer on top of the runtime, not the default path, and it's
   off unless you call :meth:`Ormica.plan`.

Give it a goal and a brain, and it asks the brain to break the goal into concrete
subtasks — with optional routing (``target``) and dependencies (``depends_on``) —
parses the result into a :class:`Plan`, and converts it into runtime
:class:`~ormica.runtime.Task` objects in dependency-respecting order.

    from ormica import Ormica
    from ormica.brain import ClaudeBrain
    from ormica.planner import Planner

    plan = Planner(ClaudeBrain()).plan("Launch the Q3 newsletter", max_depth=2)
    print(plan.pretty())
    org.enqueue_plan(plan)
    org.run(brain=ClaudeBrain())

Decomposition is *structured*: the brain is asked for JSON, and dependencies are
expressed as 1-based indices into the returned step list (easy for a model to
get right), which the planner maps to stable step ids. ``max_depth > 1``
recursively decomposes each step until the model can't break it down further,
producing a plan tree whose **leaves** are the actual work.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

from .brain import AsyncBrain, Brain, Prompt
from .runtime import Task


class PlanError(RuntimeError):
    """Raised when a plan can't be parsed, or its dependencies are invalid."""


def _new_id() -> str:
    return uuid4().hex[:8]


@dataclass
class PlannedStep:
    """One subtask in a plan.

    ``depends_on`` holds ids of sibling steps that must finish first.
    ``substeps`` is populated when the step is recursively decomposed; a step
    with no substeps is a *leaf* — the unit that becomes a runnable Task.
    """

    description: str
    target: str = ""
    priority: str = "normal"
    depends_on: list[str] = field(default_factory=list)
    id: str = field(default_factory=_new_id)
    substeps: list["PlannedStep"] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return not self.substeps


@dataclass
class Plan:
    """A decomposition of ``goal`` into a tree of :class:`PlannedStep`."""

    goal: str
    steps: list[PlannedStep] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.steps)

    def __iter__(self):
        return iter(self.steps)

    def leaves(self) -> list[PlannedStep]:
        """Every leaf step (the actual work), depth-first."""
        out: list[PlannedStep] = []

        def walk(steps: list[PlannedStep]) -> None:
            for s in steps:
                if s.is_leaf:
                    out.append(s)
                else:
                    walk(s.substeps)

        walk(self.steps)
        return out

    def topological_order(self) -> list[PlannedStep]:
        """Top-level steps ordered so dependencies come first."""
        return _toposort(self.steps)

    def to_tasks(self) -> list[Task]:
        """Flatten leaves into runnable Tasks, carrying dependencies as task ids.

        Each level is topologically sorted by ``depends_on``; the tree is walked
        depth-first so a parent's subtree is a contiguous, ordered block (the
        sequential runner executes in this order). Each leaf Task's
        ``depends_on`` is set to the ids of the leaf Tasks it must wait on — its
        own step dependencies **plus** any inherited from ancestor steps, and a
        dependency on a decomposed step expands to all that step's leaves. Feed
        the result to :meth:`Ormica.arun_dag` for parallel, DAG-aware execution.
        """
        leaf_task: dict[str, Task] = {}
        ordered: list[Task] = []

        # Pass 1: a Task per leaf, in dependency-respecting DFS order.
        def build(steps: list[PlannedStep]) -> None:
            for s in _toposort(steps):
                if s.is_leaf:
                    t = Task(
                        description=s.description,
                        target=s.target,
                        priority=s.priority,
                    )
                    leaf_task[s.id] = t
                    ordered.append(t)
                else:
                    build(s.substeps)

        build(self.steps)

        # Index: every step id -> the leaf Task ids in its subtree.
        leaves_by_step: dict[str, list[str]] = {}

        def index(steps: list[PlannedStep]) -> list[str]:
            collected: list[str] = []
            for s in steps:
                under = [leaf_task[s.id].id] if s.is_leaf else index(s.substeps)
                leaves_by_step[s.id] = under
                collected.extend(under)
            return collected

        index(self.steps)

        # Pass 2: attach dependencies (own + inherited), translated to task ids.
        def attach(steps: list[PlannedStep], inherited: list[str]) -> None:
            for s in steps:
                dep_step_ids = inherited + list(s.depends_on)
                if s.is_leaf:
                    task = leaf_task[s.id]
                    dep_task_ids: list[str] = []
                    for dsid in dep_step_ids:
                        dep_task_ids.extend(leaves_by_step.get(dsid, []))
                    task.depends_on = [
                        d for d in dict.fromkeys(dep_task_ids) if d != task.id
                    ]
                else:
                    attach(s.substeps, dep_step_ids)

        attach(self.steps, [])
        return ordered

    def pretty(self) -> str:
        """A human-readable tree render of the plan."""
        lines = [f"Goal: {self.goal}"]

        def walk(steps: list[PlannedStep], depth: int) -> None:
            for s in _toposort(steps):
                prefix = "  " * depth + "- "
                bits = [s.description]
                if s.target:
                    bits.append(f"@{s.target}")
                if s.depends_on:
                    bits.append(f"(after {len(s.depends_on)})")
                lines.append(prefix + " ".join(bits))
                walk(s.substeps, depth + 1)

        walk(self.steps, 1)
        return "\n".join(lines)


def _toposort(steps: list[PlannedStep]) -> list[PlannedStep]:
    """Kahn's algorithm, stable on original order. Raises on cycle/unknown dep."""
    by_id = {s.id: s for s in steps}
    indeg = {s.id: 0 for s in steps}
    dependents: dict[str, list[str]] = {s.id: [] for s in steps}
    for s in steps:
        for dep in s.depends_on:
            if dep not in by_id:
                raise PlanError(
                    f"step {s.id!r} depends on unknown step {dep!r}"
                )
            dependents[dep].append(s.id)
            indeg[s.id] += 1

    order: list[PlannedStep] = []
    ready = [s.id for s in steps if indeg[s.id] == 0]  # original order preserved
    while ready:
        sid = ready.pop(0)
        order.append(by_id[sid])
        for nxt in dependents[sid]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)

    if len(order) != len(steps):
        raise PlanError("plan has a dependency cycle")
    return order


# --- parsing ------------------------------------------------------------------


def _extract_json(text: str) -> str:
    """Pull the first JSON object/array out of a possibly prose-wrapped reply."""
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    text = text.strip()
    start = min(
        (i for i in (text.find("{"), text.find("[")) if i != -1),
        default=-1,
    )
    if start == -1:
        raise PlanError("no JSON found in planner response")
    # Walk to the matching closing bracket.
    open_ch = text[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    for i in range(start, len(text)):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise PlanError("unbalanced JSON in planner response")


def _parse_steps(text: str) -> list[PlannedStep]:
    """Parse the wire format into flat PlannedSteps.

    Wire format (dependencies are 1-based indices into the list)::

        {"steps": [
            {"description": "...", "target": "sales",
             "priority": "high", "depends_on": []},
            {"description": "...", "depends_on": [1]}
        ]}

    A bare list is also accepted.
    """
    try:
        data = json.loads(_extract_json(text))
    except (ValueError, TypeError) as exc:
        raise PlanError(f"planner response was not valid JSON: {exc}") from exc

    raw = data.get("steps", []) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise PlanError("planner response must be a list of steps")

    steps: list[PlannedStep] = []
    for item in raw:
        if isinstance(item, str):
            item = {"description": item}
        if not isinstance(item, dict) or not item.get("description"):
            raise PlanError(f"invalid step: {item!r}")
        steps.append(
            PlannedStep(
                description=str(item["description"]).strip(),
                target=str(item.get("target", "") or ""),
                priority=str(item.get("priority", "normal") or "normal"),
            )
        )

    # Resolve 1-based index dependencies to step ids, now that ids exist.
    for item, step in zip(raw, steps):
        deps = item.get("depends_on", []) if isinstance(item, dict) else []
        for d in deps or []:
            idx = int(d) - 1
            if not (0 <= idx < len(steps)) or steps[idx] is step:
                raise PlanError(
                    f"step {step.description!r} has invalid depends_on {d!r}"
                )
            step.depends_on.append(steps[idx].id)
    return steps


def _build_prompt(goal: str, targets: Optional[list[str]]) -> str:
    target_line = ""
    if targets:
        target_line = (
            "\nRoute each subtask by setting \"target\" to one of: "
            + ", ".join(targets)
            + "."
        )
    return (
        "Decompose the following goal into concrete, independently executable "
        "subtasks. Return ONLY JSON of the form:\n"
        '{"steps": [{"description": str, "target": str (optional), '
        '"priority": "high"|"normal"|"low" (optional), '
        '"depends_on": [1-based indices of prerequisite steps] (optional)}]}\n'
        "If a subtask needs another to finish first, list that step's index in "
        "depends_on. Keep descriptions specific and actionable."
        + target_line
        + f"\n\nGoal: {goal}"
    )


# --- planners -----------------------------------------------------------------


class _PlannerBase:
    def _parse(self, goal: str, content: str) -> list[PlannedStep]:
        return _parse_steps(content)


class Planner(_PlannerBase):
    """Decomposes a goal into a :class:`Plan` using a sync :class:`Brain`."""

    def __init__(self, brain: Brain, *, max_tokens: int = 1024) -> None:
        self.brain = brain
        self.max_tokens = max_tokens

    def plan(
        self,
        goal: str,
        *,
        targets: Optional[list[str]] = None,
        max_depth: int = 1,
    ) -> Plan:
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        steps = self._decompose(goal, targets)
        for step in steps:
            self._expand(step, targets, max_depth)
        return Plan(goal=goal, steps=steps)

    def _decompose(
        self, goal: str, targets: Optional[list[str]]
    ) -> list[PlannedStep]:
        prompt: Prompt = _build_prompt(goal, targets)
        response = self.brain.think(prompt, max_tokens=self.max_tokens)
        return self._parse(goal, response.content)

    def _expand(
        self, step: PlannedStep, targets: Optional[list[str]], depth: int
    ) -> None:
        if depth <= 1:
            return
        subs = self._decompose(step.description, targets)
        if len(subs) <= 1:  # model couldn't break it down further — atomic leaf
            return
        step.substeps = subs
        for s in subs:
            self._expand(s, targets, depth - 1)


class AsyncPlanner(_PlannerBase):
    """Async sibling of :class:`Planner` — uses an :class:`AsyncBrain`."""

    def __init__(self, brain: AsyncBrain, *, max_tokens: int = 1024) -> None:
        self.brain = brain
        self.max_tokens = max_tokens

    async def plan(
        self,
        goal: str,
        *,
        targets: Optional[list[str]] = None,
        max_depth: int = 1,
    ) -> Plan:
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        steps = await self._decompose(goal, targets)
        for step in steps:
            await self._expand(step, targets, max_depth)
        return Plan(goal=goal, steps=steps)

    async def _decompose(
        self, goal: str, targets: Optional[list[str]]
    ) -> list[PlannedStep]:
        prompt: Prompt = _build_prompt(goal, targets)
        response = await self.brain.think(prompt, max_tokens=self.max_tokens)
        return self._parse(goal, response.content)

    async def _expand(
        self, step: PlannedStep, targets: Optional[list[str]], depth: int
    ) -> None:
        if depth <= 1:
            return
        subs = await self._decompose(step.description, targets)
        if len(subs) <= 1:
            return
        step.substeps = subs
        for s in subs:
            await self._expand(s, targets, depth - 1)
