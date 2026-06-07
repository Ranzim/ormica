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
        max_depth: int = 8,
        memory: Optional[Mycelium] = None,
        memory_path: Optional[str] = None,
        memory_db: Optional[str] = None,
        signals_half_life: float = 60.0,
        constitution: Optional[Any] = None,
    ) -> None:
        from ormica.cortex import ConstitutionPolicy
        from ormica.observe import EventBus

        # If a Constitution is supplied, it governs spawn permission too —
        # composing with any user-supplied SpawnPolicy.
        if constitution is not None:
            policy = ConstitutionPolicy(constitution, inner=policy)
        self.constitution = constitution
        self.tree = Tree(name, owner=owner, max_depth=max_depth, policy=policy)
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
        self.signals = Stigma(self.memory, half_life=signals_half_life)
        self.events: EventBus = EventBus()
        self._tasks: list = []

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

    @property
    def tasks(self) -> list:
        return list(self._tasks)

    def pending_tasks(self) -> list:
        return [t for t in self._tasks if t.status == "pending"]

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
        return runner.run(self.pending_tasks())

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
        return await runner.run(self.pending_tasks())

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
