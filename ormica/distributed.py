"""Distributed execution — many workers draining one shared queue, stigmergically.

There is no dispatcher handing out work. Every worker runs the same loop against
a **shared** mycelium: reload the task queue, find a task whose dependencies are
done, win an exclusive **lease** on it (so no two workers run the same task),
execute it, checkpoint the result back, repeat. Coordination lives entirely in
the shared substrate — the stigmergic principle applied to compute.

Point N processes at one durable, claimable backend (``SqliteBackend`` on a
shared path) and each becomes a worker:

    org = Ormica("HQ", memory=Mycelium(backend=SqliteBackend("colony.db")))
    org.run_worker(brain=brain, worker_id="worker-3")

Crash safety comes from lease TTLs: if a worker dies mid-task, its lease expires
and another worker reclaims the task — the same forgiveness the durable-run
:meth:`~ormica.Ormica.resume` gives, now across machines.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from ormica.mycelium import ClaimableBackend


class DistributedWorker:
    """One worker draining the org's shared task queue via atomic leases.

    ``worker_id`` must be unique per worker. ``lease_ttl`` bounds how long a
    claimed task is protected before another worker may reclaim it (set it
    comfortably above your slowest task). The worker stops when no runnable
    task remains after ``idle_rounds`` empty polls — so a fleet of workers all
    exit once the queue is drained.
    """

    def __init__(
        self,
        org: Any,
        brain: Any,
        *,
        worker_id: str,
        lease_ttl: float = 30.0,
        max_tasks: int = 1000,
        idle_rounds: int = 1,
        poll: float = 0.0,
    ) -> None:
        backend = org.memory.backend
        if not isinstance(backend, ClaimableBackend):
            raise TypeError(
                "distributed execution needs a ClaimableBackend (e.g. "
                "SqliteBackend for cross-process, or the default InMemoryBackend "
                "for in-process threads); this mycelium's backend is "
                f"{type(backend).__name__}"
            )
        self.org = org
        self.brain = brain
        self.worker_id = worker_id
        self.lease_ttl = lease_ttl
        self.max_tasks = max_tasks
        self.idle_rounds = idle_rounds
        self.poll = poll

    # --- coordination ---

    def _claim(self, task: Any) -> bool:
        return self.org.memory.backend.claim(
            f"tasks/{task.id}",
            self.worker_id,
            ttl=self.lease_ttl,
            now=self.org.memory.now(),
        )

    def _release(self, task: Any) -> None:
        self.org.memory.backend.release(f"tasks/{task.id}", self.worker_id)

    def _runnable(self, tasks: list) -> list:
        """Pending tasks whose in-queue prerequisites have all reached done."""
        done = {t.id for t in tasks if t.status == "done"}
        ids = {t.id for t in tasks}
        return [
            t
            for t in tasks
            if t.status == "pending"
            and all(d in done for d in t.depends_on if d in ids)
        ]

    def _publish(self) -> None:
        """Seed the shared queue with this process's local tasks, idempotently.

        Tasks created via ``org.task(...)`` live in memory until a runner
        checkpoints them. A worker persists them to the shared mycelium so every
        worker can see them — but never clobbers a record already there, so it
        can't overwrite another worker's progress on a shared backend.
        """
        from ormica.runtime import _record_task

        for task in getattr(self.org, "_tasks", []):
            if f"tasks/{task.id}" not in self.org.memory:
                _record_task(self.org, task, self.org.root)

    def run(self):
        """Drain runnable tasks until the queue is empty. Returns this worker's tally."""
        from ormica.runtime import RunResult

        self._publish()
        tally = RunResult()
        idle = 0
        while tally.processed < self.max_tasks:
            tasks = self.org.load_tasks()
            by_id = {t.id: t for t in tasks}
            claimed = self._try_claim_one(self._runnable(tasks))

            if claimed is None:
                # Nothing to take right now. If work is still in flight elsewhere
                # (running, or pending behind a running prerequisite), wait and
                # retry; otherwise the queue is drained and we can stop.
                if not any(t.status in ("pending", "running") for t in tasks):
                    break
                idle += 1
                if idle >= self.idle_rounds:
                    break
                if self.poll:
                    time.sleep(self.poll)
                continue

            idle = 0
            try:
                self._execute(claimed, by_id)
            finally:
                self._release(claimed)
            tally.processed += 1
            if claimed.status == "done":
                tally.succeeded += 1
            elif claimed.status == "failed":
                tally.failed += 1
        return tally

    def _try_claim_one(self, runnable: list) -> Optional[Any]:
        """Win a lease on the first runnable task still pending after the claim."""
        from ormica.runtime import _PRIORITY_RANK

        for task in sorted(
            runnable, key=lambda t: (_PRIORITY_RANK.get(t.priority, 99), t.created_at)
        ):
            if not self._claim(task):
                continue
            # Re-read: another worker may have finished (and released) it between
            # our load and our claim. Only run it if it's still pending.
            fresh = self.org.memory.get(f"tasks/{task.id}")
            if isinstance(fresh, dict) and fresh.get("status") != "pending":
                self._release(task)
                continue
            return task
        return None

    # --- execution (mirrors TaskRunner._process, reusing the shared helpers) ---

    def _execute(self, task: Any, by_id: dict) -> None:
        from ormica.agent import Agent
        from ormica.observe import TASK_DONE, TASK_FAILED, TASK_STARTED
        from ormica.runtime import (
            _brain_for,
            _build_tools,
            _capture_result,
            _dep_prompt,
            _maybe_auto_emit,
            _record_task,
            _resolve_target,
        )

        task.status = "running"
        _record_task(self.org, task, self.org.root)  # durable "running" checkpoint
        self.org.events.emit(
            TASK_STARTED,
            source="worker",
            task_id=task.id,
            worker=self.worker_id,
            target=task.target,
            description=task.description,
        )

        record_author = self.org.root
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
            prompt = _dep_prompt(task, by_id)
            response = (
                agent.act_with_tools(prompt, tools=tools) if tools else agent.act(prompt)
            )
            _capture_result(task, response)
        except Exception as exc:  # noqa: BLE001 — one bad task must not kill the worker
            task.error = f"{type(exc).__name__}: {exc}"
            task.status = "failed"
        finally:
            _record_task(self.org, task, record_author)
            _maybe_auto_emit(self.org, task, record_author)
            if task.status == "done":
                self.org.events.emit(
                    TASK_DONE, source="worker", task_id=task.id,
                    worker=self.worker_id, target=task.target,
                )
            elif task.status == "failed":
                self.org.events.emit(
                    TASK_FAILED, source="worker", task_id=task.id,
                    worker=self.worker_id, target=task.target, error=task.error,
                )
