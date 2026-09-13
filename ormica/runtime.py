"""Task, TaskRunner, AsyncTaskRunner — work queue + execution loops."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import time
from typing import TYPE_CHECKING, Any, Callable, Optional, Union
from uuid import uuid4

from .agent import Agent, AsyncAgent
from .arbor import Node
from .brain import AsyncBrain, Brain, Router
from .observe import (
    RUN_COMPLETED,
    RUN_STARTED,
    TASK_DONE,
    TASK_FAILED,
    TASK_STARTED,
)

if TYPE_CHECKING:
    from .core import Ormica


_PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


def _new_id() -> str:
    return uuid4().hex[:8]


@dataclass
class Task:
    """One unit of work for the org.

    Holds the request (``description``), where it should be routed
    (``target`` — a node name; root if empty), priority, and the
    runtime state and result populated by a runner.
    """

    description: str
    target: str = ""
    priority: str = "normal"
    id: str = field(default_factory=_new_id)
    status: str = "pending"  # pending | running | done | failed
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time)
    # ids of tasks that must reach ``done`` before this one may run. Empty for
    # a flat queue; populated by the planner (or you) to form a DAG that
    # :class:`AsyncDagRunner` executes with maximum safe parallelism.
    depends_on: list[str] = field(default_factory=list)

    @classmethod
    def from_record(cls, payload: dict) -> "Task":
        """Reconstruct a Task from a persisted ``tasks/{id}`` record."""
        return cls(
            description=payload["description"],
            target=payload.get("target", ""),
            priority=payload.get("priority", "normal"),
            id=payload["id"],
            status=payload.get("status", "pending"),
            result=payload.get("result"),
            error=payload.get("error"),
            created_at=payload.get("created_at", time()),
            depends_on=list(payload.get("depends_on", [])),
        )


@dataclass
class RunResult:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    tokens_used: int = 0


BrainOrRouter = Union[Brain, Router]
AsyncBrainOrRouter = Union[AsyncBrain, Router]
TaskCallback = Callable[[Task], None]


# --- shared helpers (used by both runners) -----------------------------------


def _resolve_target(org: "Ormica", target: str) -> Node:
    if not target:
        return org.root
    return org.find(target)


def _brain_for(brain_or_router: Any, node: Node) -> Any:
    if isinstance(brain_or_router, Router):
        return brain_or_router.for_node(node)
    return brain_or_router


def _record_task(org: "Ormica", task: Task, author: Node) -> None:
    payload: dict[str, Any] = {
        "id": task.id,
        "description": task.description,
        "target": task.target,
        "priority": task.priority,
        "status": task.status,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at,
        "depends_on": list(task.depends_on),
    }
    org.memory.write(f"tasks/{task.id}", payload, author=author.id)


def _checkpoint_queue(org: "Ormica", queue: list[Task]) -> None:
    """Persist every queued task up front so a crash before/mid-run is resumable.

    Without this, only tasks that have *finished* are durable; pending tasks
    live only in RAM. Recording them at run start means :meth:`Ormica.resume`
    can reload the full queue and re-run whatever didn't reach ``done``.
    """
    for task in queue:
        _record_task(org, task, org.root)


def _build_emit_tool(org: "Ormica", node: Node):
    """If the node declares emit_tool_config, build a fresh EmitToolBuilder + Tool.

    Per-task — each task gets a new builder so the rate-limit counter
    starts at zero. Returns ``(builder, tool)`` or ``(None, None)`` when
    the node has no emit_tool declared (back-compat path).
    """
    cfg = node.meta.get("emit_tool_config")
    if cfg is None:
        return None, None
    from ormica.stigma import EmitToolBuilder

    builder = EmitToolBuilder(org.signals, node, cfg)
    return builder, builder.as_tool()


def _build_message_tool(org: "Ormica", node: Node):
    """Build the LLM-facing send_message tool if the node declares one.

    Reads ``node.meta["message_tool_config"]`` (a
    :class:`~ormica.postbox.MessageToolConfig`). Recipient names are resolved
    to node ids via ``org.find``. Returns the Tool or ``None``.
    """
    cfg = node.meta.get("message_tool_config")
    if cfg is None:
        return None
    from ormica.postbox import MessageToolBuilder

    builder = MessageToolBuilder(
        org.postbox, node, cfg, resolve=lambda name: org.find(name).id
    )
    return builder.as_tool()


def _build_tools(org: "Ormica", node: Node) -> list:
    """Assemble every LLM-facing tool a node has declared (emit + message)."""
    tools: list = []
    _, emit_tool = _build_emit_tool(org, node)
    if emit_tool is not None:
        tools.append(emit_tool)
    message_tool = _build_message_tool(org, node)
    if message_tool is not None:
        tools.append(message_tool)
    return tools


def _maybe_auto_emit(org: "Ormica", task: Task, node: Node) -> None:
    """Reinforce stigma trails after a task finalizes.

    Two layers, both swallow exceptions so a stigma write failure never
    turns a successful task into a failed one:

    1. Org-wide auto-emit (gated on ``org.signals_auto_emit``):
       reinforces ``activity:<node.id>`` and ``topic:<task.target>``.
       Provides a default "what's been busy" signal landscape with no
       per-node configuration.

    2. Per-node declared emits (always on when present): reads
       ``node.meta["emits"]`` — a list of ``(topic, strength)`` pairs
       stamped by ``AgentTemplate.plant()`` when a colony template
       declares ``emits:`` in yaml. Lets a colony author publish a
       domain-meaningful topic vocabulary (e.g. ``trending:weekly-shifts``)
       without writing a custom Agent.

    ``reinforce`` (not ``emit``) so repeated work accumulates a trail
    instead of clobbering itself at the declared strength each time.
    """
    try:
        if getattr(org, "signals_auto_emit", False):
            org.signals.reinforce(f"activity:{node.id}", amount=0.5, by=node.id)
            if task.target:
                org.signals.reinforce(
                    f"topic:{task.target}", amount=0.5, by=node.id
                )
        for topic, strength in node.meta.get("emits", ()):
            org.signals.reinforce(topic, amount=float(strength), by=node.id)
    except Exception:
        pass


def _sorted_queue(tasks: list[Task], max_tasks: int) -> list[Task]:
    return sorted(
        tasks,
        key=lambda t: (_PRIORITY_RANK.get(t.priority, 99), t.created_at),
    )[:max_tasks]


def _tally(queue: list[Task]) -> RunResult:
    result = RunResult()
    for t in queue:
        result.processed += 1
        if t.status == "done":
            result.succeeded += 1
        elif t.status == "failed":
            result.failed += 1
    return result


# --- sync runner --------------------------------------------------------------


class TaskRunner:
    """Processes an org's task queue sequentially.

    For each task: resolve the target node, build an ``Agent`` around it
    using the supplied brain (a single :class:`Brain` or a :class:`Router`
    for per-node selection), call ``agent.act(task.description)``, and
    record the result on the task and in shared memory under ``tasks/{id}``.

    Failures mark the task ``failed`` and the loop continues — one bad
    task does not abort the whole run.
    """

    def __init__(
        self,
        org: "Ormica",
        *,
        brain: BrainOrRouter,
        max_tasks: int = 100,
        on_task_start: Optional[TaskCallback] = None,
        on_task_done: Optional[TaskCallback] = None,
    ) -> None:
        if max_tasks < 1:
            raise ValueError("max_tasks must be >= 1")
        self.org = org
        self.brain = brain
        self.max_tasks = max_tasks
        self.on_task_start = on_task_start
        self.on_task_done = on_task_done

    def run(self, tasks: list[Task]) -> RunResult:
        queue = _sorted_queue(tasks, self.max_tasks)
        _checkpoint_queue(self.org, queue)
        self.org.events.emit(RUN_STARTED, source="runner", n_tasks=len(queue), mode="sync")
        for task in queue:
            self._process(task)
        result = _tally(queue)
        self.org.events.emit(
            RUN_COMPLETED,
            source="runner",
            processed=result.processed,
            succeeded=result.succeeded,
            failed=result.failed,
        )
        return result

    def _process(self, task: Task) -> None:
        task.status = "running"
        _record_task(self.org, task, self.org.root)  # durable "running" checkpoint
        self.org.events.emit(
            TASK_STARTED,
            source="runner",
            task_id=task.id,
            target=task.target,
            priority=task.priority,
            description=task.description,
        )
        if self.on_task_start is not None:
            self.on_task_start(task)

        record_author = self.org.root
        tokens_used = 0
        try:
            node = _resolve_target(self.org, task.target)
            record_author = node
            brain = _brain_for(self.brain, node)
            agent = Agent(
                node,
                brain,
                memory=self.org.memory,
                signals=self.org.signals,
                constitution=self.org.constitution,
                budget=self.org.budget,
            )
            agent.events = self.org.events
            agent.task_id = task.id
            agent.runtime_task = task
            tools = _build_tools(self.org, node)
            if tools:
                response = agent.act_with_tools(task.description, tools=tools)
            else:
                response = agent.act(task.description)
            tokens_used = response.tokens_used
            task.result = response.content
            task.status = "done"
        except Exception as exc:
            task.error = f"{type(exc).__name__}: {exc}"
            task.status = "failed"
        finally:
            _record_task(self.org, task, record_author)
            _maybe_auto_emit(self.org, task, record_author)
            if task.status == "done":
                self.org.events.emit(
                    TASK_DONE,
                    source="runner",
                    task_id=task.id,
                    target=task.target,
                    tokens_used=tokens_used,
                )
            elif task.status == "failed":
                self.org.events.emit(
                    TASK_FAILED,
                    source="runner",
                    task_id=task.id,
                    target=task.target,
                    error=task.error,
                )
            if self.on_task_done is not None:
                self.on_task_done(task)


# --- async runner -------------------------------------------------------------


class AsyncTaskRunner:
    """Async sibling of :class:`TaskRunner`.

    Tasks are grouped into priority bands (``high`` → ``normal`` → ``low``).
    Each band is fanned out via :func:`asyncio.gather`, capped by
    ``concurrency``. Bands run sequentially so a queued ``high`` task
    blocks a ``normal`` one — within a band tasks race freely.
    """

    def __init__(
        self,
        org: "Ormica",
        *,
        brain: AsyncBrainOrRouter,
        max_tasks: int = 100,
        concurrency: int = 5,
        on_task_start: Optional[TaskCallback] = None,
        on_task_done: Optional[TaskCallback] = None,
    ) -> None:
        if max_tasks < 1:
            raise ValueError("max_tasks must be >= 1")
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self.org = org
        self.brain = brain
        self.max_tasks = max_tasks
        self.concurrency = concurrency
        self.on_task_start = on_task_start
        self.on_task_done = on_task_done

    async def run(self, tasks: list[Task]) -> RunResult:
        queue = _sorted_queue(tasks, self.max_tasks)
        _checkpoint_queue(self.org, queue)
        self.org.events.emit(
            RUN_STARTED,
            source="runner",
            n_tasks=len(queue),
            mode="async",
            concurrency=self.concurrency,
        )

        bands: dict[int, list[Task]] = {}
        for t in queue:
            rank = _PRIORITY_RANK.get(t.priority, 99)
            bands.setdefault(rank, []).append(t)

        sem = asyncio.Semaphore(self.concurrency)
        for rank in sorted(bands):
            band = bands[rank]
            await asyncio.gather(*(self._bounded(t, sem) for t in band))

        result = _tally(queue)
        self.org.events.emit(
            RUN_COMPLETED,
            source="runner",
            processed=result.processed,
            succeeded=result.succeeded,
            failed=result.failed,
        )
        return result

    async def _bounded(self, task: Task, sem: asyncio.Semaphore) -> None:
        async with sem:
            await self._process(task)

    async def _process(self, task: Task) -> None:
        task.status = "running"
        _record_task(self.org, task, self.org.root)  # durable "running" checkpoint
        self.org.events.emit(
            TASK_STARTED,
            source="runner",
            task_id=task.id,
            target=task.target,
            priority=task.priority,
            description=task.description,
        )
        if self.on_task_start is not None:
            self.on_task_start(task)

        record_author = self.org.root
        tokens_used = 0
        try:
            node = _resolve_target(self.org, task.target)
            record_author = node
            brain = _brain_for(self.brain, node)
            agent = AsyncAgent(
                node,
                brain,
                memory=self.org.memory,
                signals=self.org.signals,
                constitution=self.org.constitution,
                budget=self.org.budget,
            )
            agent.events = self.org.events
            agent.task_id = task.id
            agent.runtime_task = task
            tools = _build_tools(self.org, node)
            if tools:
                response = await agent.act_with_tools(
                    task.description, tools=tools
                )
            else:
                response = await agent.act(task.description)
            tokens_used = response.tokens_used
            task.result = response.content
            task.status = "done"
        except Exception as exc:
            task.error = f"{type(exc).__name__}: {exc}"
            task.status = "failed"
        finally:
            _record_task(self.org, task, record_author)
            _maybe_auto_emit(self.org, task, record_author)
            if task.status == "done":
                self.org.events.emit(
                    TASK_DONE,
                    source="runner",
                    task_id=task.id,
                    target=task.target,
                    tokens_used=tokens_used,
                )
            elif task.status == "failed":
                self.org.events.emit(
                    TASK_FAILED,
                    source="runner",
                    task_id=task.id,
                    target=task.target,
                    error=task.error,
                )
            if self.on_task_done is not None:
                self.on_task_done(task)


# --- DAG runner ---------------------------------------------------------------


def _detect_cycle(deps: dict[str, list[str]]) -> None:
    """Raise ValueError if the dependency graph has a cycle (Kahn's)."""
    indeg = {tid: len(ds) for tid, ds in deps.items()}
    dependents: dict[str, list[str]] = {tid: [] for tid in deps}
    for tid, ds in deps.items():
        for d in ds:
            dependents[d].append(tid)
    ready = [tid for tid, n in indeg.items() if n == 0]
    seen = 0
    while ready:
        cur = ready.pop()
        seen += 1
        for nxt in dependents[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
    if seen != len(deps):
        raise ValueError("task graph has a dependency cycle")


class AsyncDagRunner(AsyncTaskRunner):
    """Runs tasks respecting ``depends_on`` — maximum safe parallelism.

    A task runs only once every task it depends on has reached ``done``.
    Independent tasks race concurrently (capped by ``concurrency``). If a
    prerequisite ``failed``, every task downstream of it is skipped (marked
    failed with a "prerequisite failed" reason) rather than run against an
    incomplete input. Reuses :class:`AsyncTaskRunner`'s per-task execution.
    """

    async def run(self, tasks: list[Task]) -> RunResult:
        queue = _sorted_queue(tasks, self.max_tasks)
        _checkpoint_queue(self.org, queue)
        by_id = {t.id: t for t in queue}
        # Only honor dependencies that point inside this queue.
        deps = {t.id: [d for d in t.depends_on if d in by_id] for t in queue}
        _detect_cycle(deps)

        indeg = {tid: len(deps[tid]) for tid in by_id}
        dependents: dict[str, list[str]] = {tid: [] for tid in by_id}
        for tid, ds in deps.items():
            for d in ds:
                dependents[d].append(tid)

        self.org.events.emit(
            RUN_STARTED,
            source="runner",
            n_tasks=len(queue),
            mode="dag",
            concurrency=self.concurrency,
        )

        remaining = set(by_id)
        launched: set[str] = set()
        sem = asyncio.Semaphore(self.concurrency)

        async def _run_one(t: Task) -> Task:
            await self._bounded(t, sem)
            return t

        def _block_downstream(failed_id: str) -> None:
            stack = list(dependents[failed_id])
            while stack:
                tid = stack.pop()
                if tid not in remaining or tid in launched:
                    continue
                blocked = by_id[tid]
                blocked.status = "failed"
                blocked.error = f"skipped: prerequisite {failed_id} failed"
                _record_task(self.org, blocked, self.org.root)
                self.org.events.emit(
                    TASK_FAILED,
                    source="runner",
                    task_id=tid,
                    target=blocked.target,
                    error=blocked.error,
                )
                remaining.discard(tid)
                launched.add(tid)
                stack.extend(dependents[tid])

        def _schedule_ready(pending_aws: set) -> None:
            order = sorted(
                remaining,
                key=lambda i: (
                    _PRIORITY_RANK.get(by_id[i].priority, 99),
                    by_id[i].created_at,
                ),
            )
            for tid in order:
                if tid not in launched and indeg[tid] == 0:
                    launched.add(tid)
                    pending_aws.add(asyncio.create_task(_run_one(by_id[tid])))

        aws: set = set()
        _schedule_ready(aws)
        while aws:
            done, aws = await asyncio.wait(
                aws, return_when=asyncio.FIRST_COMPLETED
            )
            for fut in done:
                finished = fut.result()
                remaining.discard(finished.id)
                if finished.status == "done":
                    for dep in dependents[finished.id]:
                        indeg[dep] -= 1
                else:
                    _block_downstream(finished.id)
            _schedule_ready(aws)

        result = _tally(queue)
        self.org.events.emit(
            RUN_COMPLETED,
            source="runner",
            processed=result.processed,
            succeeded=result.succeeded,
            failed=result.failed,
        )
        return result
