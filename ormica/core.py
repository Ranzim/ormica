"""The Ormica facade — one entry point that wires arbor, canopy, mycelium, and stigma."""
from __future__ import annotations

from typing import Any, Iterator, Optional, Union

from ormica.arbor import Node, NodeNotFound, SpawnPolicy, Tree
from ormica.mycelium import Entry, Mycelium, Scope
from ormica.stigma import Signal, Stigma

ParentRef = Union[Node, str, None]
NodeRef = Union[Node, str]


class Ormica:
    """A self-organizing colony — root node, shared memory, signals, permission chain.

    Wires :class:`Tree`, :class:`Mycelium`, and :class:`Stigma` together.
    Canopy plugs in through the ``policy`` argument exactly as it would on
    a bare ``Tree``.

    Example::

        org = Ormica("My Company", owner="Founder")
        ops = org.spawn("ops")
        org.spawn("scout", under=ops)
        org.emit("lead_found", strength=1.0)
    """

    def __init__(
        self,
        name: str,
        owner: str = "",
        *,
        policy: Optional[SpawnPolicy] = None,
        spawn_governor: Optional[SpawnPolicy] = None,
        budget: Optional[Any] = None,
        max_depth: int = 8,
        memory: Optional[Mycelium] = None,
        memory_path: Optional[str] = None,
        memory_db: Optional[str] = None,
        signals_half_life: float = 60.0,
        signals_floor: float = 0.01,
        signals_auto_emit: bool = False,
        signals_auto_evaporate: bool = False,
        constitution: Optional[Any] = None,
    ) -> None:
        from ormica.cortex import Constitution as _Constitution
        from ormica.cortex import ConstitutionPolicy
        from ormica.observe import EventBus

        # If a Constitution is supplied, it governs spawn permission too —
        # composing with any user-supplied SpawnPolicy. Without a Constitution
        # and without an explicit policy, still install an empty
        # ConstitutionPolicy so per-node spawn rules (attached to a Node via
        # ``node.rules``) cascade by default.
        # A spawn governor (economic ceilings) composes as the inner policy:
        # it chains the user's policy and is itself wrapped by ConstitutionPolicy
        # so per-node spawn rules still cascade.
        if spawn_governor is not None:
            if policy is not None and getattr(spawn_governor, "inner", None) is None:
                spawn_governor.inner = policy
            base = constitution if constitution is not None else _Constitution()
            policy = ConstitutionPolicy(base, inner=spawn_governor)
        elif constitution is not None:
            policy = ConstitutionPolicy(constitution, inner=policy)
        elif policy is None:
            policy = ConstitutionPolicy(_Constitution())
        self.constitution = constitution
        # Optional shared token budget: handed to every agent by the runner, so
        # spend accumulates colony-wide and a BudgetGovernor can gate spawns on it.
        self.budget = budget
        self.tree = Tree(
            name,
            owner=owner,
            max_depth=max_depth,
            policy=policy,
            on_spawn=self._emit_spawn,
            on_prune=self._emit_prune,
        )
        if memory_db and memory_path:
            raise ValueError(
                "set memory_db OR memory_path, not both — got "
                f"memory_db={memory_db!r}, memory_path={memory_path!r}"
            )
        if memory is None and memory_db:
            from ormica.mycelium import SqliteBackend

            memory = Mycelium(backend=SqliteBackend(memory_db))
        elif memory is None and memory_path:
            from ormica.mycelium import FileBackend

            memory = Mycelium(backend=FileBackend(memory_path))
        self.memory: Mycelium = memory if memory is not None else Mycelium()
        self.signals = Stigma(
            self.memory, half_life=signals_half_life, floor=signals_floor
        )
        # Read by the runtime's task-finalize path. Off by default in the bare
        # API so existing programmatic users see no behavior change; the CLI
        # flips it on so ``ormica signals`` is meaningful after ``ormica run``.
        self.signals_auto_emit: bool = signals_auto_emit
        # When true, ``run`` / ``arun`` call ``signals.evaporate()`` after
        # processing all tasks — drops trails below floor so persistent
        # backends (sqlite) don't accumulate stale data across invocations.
        self.signals_auto_evaporate: bool = signals_auto_evaporate
        self.events: EventBus = EventBus()
        self._tasks: list = []
        # Custom tools attached per node (by node id). The runner hands these to
        # the node's agent alongside any emit/message tools it declared.
        self._node_tools: dict = {}

    def _emit_spawn(self, node) -> None:
        """Tree hook: announce a new node on the bus (live-view / audit)."""
        from ormica.observe import NODE_SPAWNED

        parent = node.parent
        self.events.emit(
            NODE_SPAWNED,
            source="arbor",
            node_id=node.id,
            name=node.name,
            role=node.role,
            parent_id=parent.id if parent is not None else None,
            parent_name=parent.name if parent is not None else None,
            depth=node.depth,
        )

    def _emit_prune(self, node, removed: int) -> None:
        """Tree hook: announce a pruned subtree on the bus."""
        from ormica.observe import NODE_PRUNED

        self.events.emit(
            NODE_PRUNED,
            source="arbor",
            node_id=node.id,
            name=node.name,
            removed=removed,
        )

    def subscribe(self, observer) -> None:
        """Register an :class:`Observer` to receive event notifications."""
        self.events.subscribe(observer)

    def trace_for(self, task_id: str):
        """Return the :class:`Trace` for a task, or ``None``.

        Looks first in mycelium under ``traces/{task_id}`` (populated by a
        :class:`TraceObserver` with ``store=self.memory``), then falls back
        to any in-memory ``TraceObserver`` currently subscribed.
        """
        from ormica.observe import Trace, TraceEntry, TraceObserver

        entry = self.memory.read(f"traces/{task_id}")
        if entry is not None and isinstance(entry.value, dict):
            data = dict(entry.value)
            entries_raw = data.pop("entries", []) or []
            data["entries"] = [TraceEntry(**e) for e in entries_raw]
            return Trace(**data)
        for obs in self.events.observers:
            if isinstance(obs, TraceObserver):
                trace = obs.for_task(task_id)
                if trace is not None:
                    return trace
        return None

    # --- identity ---

    @property
    def name(self) -> str:
        return self.tree.root.name

    @property
    def owner(self) -> str:
        return self.tree.owner

    @property
    def root(self) -> Node:
        return self.tree.root

    # --- tree ergonomics ---

    def spawn(
        self,
        name: str,
        *,
        under: ParentRef = None,
        role: str = "",
        task: str = "",
    ) -> Node:
        parent = self._resolve_parent(under)
        return self.tree.spawn(parent, name, role=role, task=task)

    def find(self, name: str) -> Node:
        """First node in depth-first order with ``name``. Raises :class:`NodeNotFound`."""
        for node in self.tree.walk():
            if node.name == name:
                return node
        raise NodeNotFound(f"no node named {name!r}")

    def find_all(self, name: str) -> list[Node]:
        return [n for n in self.tree.walk() if n.name == name]

    def prune(self, node: NodeRef) -> int:
        return self.tree.prune(self._resolve_node(node))

    # --- colony ergonomics ---

    def add(self, template: type) -> Node:
        """Plant a single AgentTemplate class as a child of the root."""
        return template.plant(self)

    def plant(self, colony_name: str) -> list[Node]:
        """Look up a colony by name and plant it under the root."""
        from ormica.colony import get_colony

        return get_colony(colony_name)().plant(self)

    # --- runtime ---

    def task(
        self,
        description: str,
        *,
        target: str = "",
        dept: Optional[str] = None,
        priority: str = "normal",
    ):
        """Append a task to the work queue. ``dept`` is an alias for ``target``."""
        from ormica.runtime import Task

        task = Task(
            description=description,
            target=target or dept or "",
            priority=priority,
        )
        self._tasks.append(task)
        return task

    def plan(
        self,
        goal: str,
        *,
        brain,
        targets: Optional[list] = None,
        max_depth: int = 1,
        max_tokens: int = 1024,
    ):
        """Decompose ``goal`` into a :class:`~ormica.planner.Plan` via ``brain``.

        Does not enqueue anything — inspect the plan (``plan.pretty()``) and
        call :meth:`enqueue_plan` when you're happy with it.
        """
        from ormica.planner import Planner

        return Planner(brain, max_tokens=max_tokens).plan(
            goal, targets=targets, max_depth=max_depth
        )

    def enqueue_plan(self, plan) -> list:
        """Append a plan's leaf steps to the queue as Tasks (dependency order).

        Returns the Tasks added, ready for a subsequent :meth:`run`.
        """
        tasks = plan.to_tasks()
        self._tasks.extend(tasks)
        return tasks

    def give_tools(self, target: NodeRef, tools: list) -> list:
        """Attach custom tools to a node (or every node with a given name).

        The runner hands these to the node's agent (via ``act_with_tools``)
        alongside any ``emit_signal`` / ``send_message`` tools it declared —
        so a node can e.g. run code in the sandbox or hit an external API.
        ``target`` is a Node or a department name. Returns the nodes affected.
        """
        if isinstance(target, Node):
            nodes = [target]
        else:
            nodes = self.find_all(target) or [self.find(target)]
        for node in nodes:
            self._node_tools.setdefault(node.id, []).extend(tools)
        return nodes

    def tools_for(self, target: NodeRef) -> list:
        """The custom tools registered for a node (or named node)."""
        node = self._resolve_node(target)
        return list(self._node_tools.get(node.id, ()))

    @property
    def tasks(self) -> list:
        return list(self._tasks)

    def pending_tasks(self) -> list:
        return [t for t in self._tasks if t.status == "pending"]

    # --- durability / resume ---

    def load_tasks(self) -> list:
        """Rebuild the task queue from persisted ``tasks/{id}`` records.

        Replaces the in-memory queue with what's on the (persistent) backend —
        the basis for resuming a run in a fresh process. Order is restored by
        ``created_at``. Requires a durable backend (sqlite/file) to survive a
        restart; with the default in-memory backend it only reflects this
        process. Returns the loaded tasks.
        """
        from ormica.runtime import Task

        loaded = [
            Task.from_record(e.value)
            for e in self.memory.all()
            if e.key.startswith("tasks/") and isinstance(e.value, dict)
        ]
        loaded.sort(key=lambda t: t.created_at)
        self._tasks = loaded
        return loaded

    def resume(self, *, brain, retry_failed: bool = False, **run_kwargs):
        """Reload persisted tasks and re-run whatever didn't finish.

        ``done`` tasks are skipped; tasks interrupted mid-flight (``running``)
        are reset to ``pending`` and re-run. Set ``retry_failed=True`` to also
        re-run tasks that previously ``failed``. Accepts the same keyword
        arguments as :meth:`run`.
        """
        for task in self.load_tasks():
            if task.status == "running":
                task.status = "pending"
            elif task.status == "failed" and retry_failed:
                task.status = "pending"
                task.error = None
        return self.run(brain=brain, **run_kwargs)

    def run(
        self,
        *,
        brain,
        max_tasks: int = 100,
        on_task_start=None,
        on_task_done=None,
    ):
        """Process all pending tasks. ``brain`` is a Brain or a Router."""
        from ormica.runtime import TaskRunner

        runner = TaskRunner(
            self,
            brain=brain,
            max_tasks=max_tasks,
            on_task_start=on_task_start,
            on_task_done=on_task_done,
        )
        result = runner.run(self.pending_tasks())
        self._maybe_evaporate()
        return result

    async def arun(
        self,
        *,
        brain,
        max_tasks: int = 100,
        concurrency: int = 5,
        on_task_start=None,
        on_task_done=None,
    ):
        """Async run — fans out same-priority tasks concurrently.

        ``brain`` is an :class:`AsyncBrain` or a :class:`Router` whose
        members are async cortexes. Bands of equal priority run via
        ``asyncio.gather`` capped at ``concurrency``; higher priority
        bands finish before lower ones start.
        """
        from ormica.runtime import AsyncTaskRunner

        runner = AsyncTaskRunner(
            self,
            brain=brain,
            max_tasks=max_tasks,
            concurrency=concurrency,
            on_task_start=on_task_start,
            on_task_done=on_task_done,
        )
        result = await runner.run(self.pending_tasks())
        self._maybe_evaporate()
        return result

    async def arun_dag(
        self,
        *,
        brain,
        max_tasks: int = 100,
        concurrency: int = 5,
        on_task_start=None,
        on_task_done=None,
    ):
        """DAG-aware async run — honors each task's ``depends_on``.

        A task runs only after every task it depends on is ``done``; independent
        tasks run concurrently (capped by ``concurrency``); tasks downstream of a
        failure are skipped. Pair with :meth:`plan` + :meth:`enqueue_plan`, which
        wire the plan's dependencies onto the tasks.
        """
        from ormica.runtime import AsyncDagRunner

        runner = AsyncDagRunner(
            self,
            brain=brain,
            max_tasks=max_tasks,
            concurrency=concurrency,
            on_task_start=on_task_start,
            on_task_done=on_task_done,
        )
        result = await runner.run(self.pending_tasks())
        self._maybe_evaporate()
        return result

    def _maybe_evaporate(self) -> None:
        """Drop trails below floor if ``signals_auto_evaporate`` is set.

        Swallow failures so an evaporate hiccup never masks a successful run.
        """
        if not getattr(self, "signals_auto_evaporate", False):
            return
        try:
            self.signals.evaporate()
        except Exception:
            pass

    # --- memory ergonomics ---

    def write(
        self,
        key: str,
        value: Any,
        *,
        by: Optional[NodeRef] = None,
        ttl: Optional[float] = None,
        meta: Optional[dict] = None,
    ) -> Entry:
        author = self._id_of(by) if by is not None else self.root.id
        return self.memory.write(key, value, author=author, ttl=ttl, meta=meta)

    def read(self, key: str) -> Optional[Entry]:
        return self.memory.read(key)

    def remember(self, key: str, default: Any = None) -> Any:
        """Value-only shortcut over :meth:`Mycelium.get`."""
        return self.memory.get(key, default=default)

    def scope(self, node: NodeRef) -> Scope:
        return self.memory.scope(self._resolve_node(node))

    # --- signal ergonomics ---

    def emit(
        self,
        topic: str,
        *,
        strength: float = 1.0,
        by: Optional[NodeRef] = None,
    ) -> Signal:
        return self.signals.emit(topic, strength=strength, by=self._by_or_root(by))

    def reinforce(
        self,
        topic: str,
        *,
        amount: float = 1.0,
        by: Optional[NodeRef] = None,
    ) -> Signal:
        return self.signals.reinforce(topic, amount=amount, by=self._by_or_root(by))

    def sense(self, topic: str) -> Optional[Signal]:
        return self.signals.sense(topic)

    def top_signals(self, n: int = 1) -> list[Signal]:
        return self.signals.top(n)

    # --- direct messaging ---

    @property
    def postbox(self):
        """A :class:`~ormica.postbox.Postbox` over this org's shared memory."""
        from ormica.postbox import Postbox

        return Postbox(self.memory)

    def send(
        self,
        sender: NodeRef,
        recipient: NodeRef,
        body: str,
        *,
        subject: str = "",
        in_reply_to: Optional[str] = None,
    ):
        """Send a direct message. ``sender``/``recipient`` are Nodes or names."""
        return self.postbox.send(
            self._resolve_node(sender).id,
            self._resolve_node(recipient).id,
            body,
            subject=subject,
            in_reply_to=in_reply_to,
        )

    def inbox(self, recipient: NodeRef, *, unread_only: bool = False) -> list:
        """Messages addressed to ``recipient`` (a Node or a name)."""
        return self.postbox.inbox(
            self._resolve_node(recipient).id, unread_only=unread_only
        )

    # --- iteration ---

    def __iter__(self) -> Iterator[Node]:
        return self.tree.walk()

    def __len__(self) -> int:
        return len(self.tree)

    def __contains__(self, item: object) -> bool:
        return item in self.tree

    def __repr__(self) -> str:
        return f"Ormica(name={self.name!r}, owner={self.owner!r}, nodes={len(self)})"

    # --- internals ---

    def _resolve_parent(self, ref: ParentRef) -> Node:
        if ref is None:
            return self.root
        return self._resolve_node(ref)

    def _resolve_node(self, ref: NodeRef) -> Node:
        if isinstance(ref, Node):
            return ref
        return self.find(ref)

    def _by_or_root(self, ref: Optional[NodeRef]) -> str:
        return self._id_of(ref) if ref is not None else self.root.id

    @staticmethod
    def _id_of(ref: NodeRef) -> str:
        return ref.id if isinstance(ref, Node) else ref
