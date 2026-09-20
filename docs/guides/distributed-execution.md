# Distributed execution

A big run doesn't have to live in one process. Point many workers — threads, or
separate processes, or separate machines — at **one shared colony** and they'll
drain its task queue together, with **no central dispatcher** and **no task run
twice**. Coordination happens entirely through the shared mycelium: the same
stigmergic principle behind pheromone signals, applied to compute.

## The idea

There is no coordinator handing out work. Every worker runs the same loop:

```
reload the shared queue ─► find a runnable task (deps done)
   ─► win an exclusive LEASE on it ─► run it ─► checkpoint the result ─► repeat
```

Because a worker must **win a lease** before running a task, two workers never
run the same one. Because the queue and its results live in the shared store,
any worker can pick up where another left off.

```
   worker-0 ─┐                              ┌─ worker-2
             ├──▶  colony.db  (mycelium) ◀──┤
   worker-1 ─┘     tasks/*   +   leases     └─ worker-3
```

## Run a worker

```python
from ormica import Ormica
from ormica.mycelium import Mycelium, SqliteBackend

org = Ormica("Colony", memory=Mycelium(backend=SqliteBackend("colony.db")))
org.task("do the thing")            # enqueue work (any number of tasks)

org.run_worker(brain=brain, worker_id="worker-1")
```

Run that same program in several processes (each with a **unique**
`worker_id`), all pointing at the same `colony.db`, and the work splits across
them. `run_worker` returns this worker's `RunResult` (`processed` / `succeeded`
/ `failed`). See [`examples/distributed_colony`](../../examples/distributed_colony)
for a complete, runnable multi-process demo.

## Requirements: a claimable backend

Leases need a backend that can grant them atomically — a **`ClaimableBackend`**:

| Backend | Claim scope | Use for |
| --- | --- | --- |
| `InMemoryBackend` (default) | one process (threads / async) | in-process fan-out, tests |
| `SqliteBackend` | **across processes / machines** (shared file) | real distributed runs |

`SqliteBackend` makes `claim()` atomic with a transactional lease table plus
`busy_timeout`, so concurrent claimers from separate processes serialize and
exactly one wins. Pass a `FileBackend` (or any non-claimable backend) and
`run_worker` raises a clear `TypeError`.

## Publishing the queue

Tasks created with `org.task(...)` live in memory until they're checkpointed. A
worker **publishes** its local queue to the shared store on start — idempotently,
never overwriting a record already there. The simplest multi-process pattern is
to have every worker build the *same* queue with **stable task ids**: the first
to start writes them, the rest are no-ops, and all of them then drain the shared
copy.

## Dependencies and results

Workers honor `depends_on`: a task is only claimed once its prerequisites are
`done`, and it receives their results (typed [artifacts](./dag-execution.md) as
labeled JSON, otherwise text) injected into its prompt — exactly like the
single-process DAG runner. A task blocked behind a **failed** prerequisite is
skipped (marked failed, transitively), so a fleet won't spin on dead work.

## Crash safety

Leases carry a TTL (`lease_ttl`, default 30s). If a worker dies mid-task, its
lease expires and another worker reclaims the job — the same forgiveness
[`resume()`](./durable-runs.md) gives, now across workers. While a healthy
worker runs a long task, a background **heartbeat** renews the lease every
`lease_ttl / 2` so it isn't reclaimed out from under it. Disable with
`run_worker(heartbeat=False)`; raise `lease_ttl` if your tasks are very long.

## Tuning

| Parameter | What it does |
| --- | --- |
| `worker_id` | unique per worker (required) |
| `lease_ttl` | seconds a claim is protected; set above your slowest task |
| `idle_rounds` | empty polls before a worker exits (so a fleet drains, then stops) |
| `poll` | seconds to wait between empty polls |
| `max_tasks` | cap on how many tasks this worker will process |
| `heartbeat` | renew a running task's lease (default `True`) |

## Related

- [Durable, resumable runs](./durable-runs.md) — the single-process foundation
- [DAG execution](./dag-execution.md) — dependencies and typed result hand-off
- [Persistence](./persistence.md) — the backends behind the shared store
