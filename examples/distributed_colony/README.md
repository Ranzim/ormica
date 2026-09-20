# Distributed Colony — many workers, one shared queue, no dispatcher

Several OS processes point at the **same** SQLite colony file and each becomes a
worker. There is no coordinator: every worker runs the same loop — reload the
shared queue, find a runnable job, win an exclusive **lease** on it, run it,
checkpoint the result — so the jobs get split with **no double execution**.

```
                    ┌──────────────────────────┐
   worker-0  ─────▶ │                          │ ◀─────  worker-2
                    │   colony.db  (mycelium)  │
   worker-1  ─────▶ │   tasks/*   +  leases    │ ◀─────  worker-3
                    └──────────────────────────┘
        each worker: claim → run → checkpoint → repeat
        coordination lives in the shared store, not in messages
```

This is the stigmergic principle behind pheromone signals, applied to compute:
workers coordinate **through the environment**, never by talking to each other.

## Run it

```bash
python examples/distributed_colony/run.py
python examples/distributed_colony/run.py --workers 6 --jobs 40 --work-ms 40
```

No API key needed — a `MockBrain` deterministically "computes" each answer. But
the coordination is real: it relies on `SqliteBackend`'s atomic `claim()` (a
transactional lease), which is exactly how separate **machines** would
coordinate over a shared database.

Sample output:

```
12/12 jobs done in 0.26s
  job-00  done     0 (by worker-1)
  job-01  done     1 (by worker-3)
  ...
split: worker-0=3, worker-1=3, worker-2=3, worker-3=3
serial ≈ 0.36s  →  ~1.4x with 4 workers
```

Each job simulates `--work-ms` of work, so with W workers wall-clock time drops
toward `jobs * work_ms / W`. Bump `--work-ms` (and `--jobs`) to make the speedup
obvious over process-startup overhead.

## How it works

1. **Shared, claimable store.** The colony's mycelium is a `SqliteBackend` on a
   path every process opens. SQLite (WAL + `busy_timeout`) makes `claim()`
   atomic across processes — at most one worker holds a task's lease at a time.
2. **Idempotent publish.** Every process builds the identical queue with stable
   job ids; the first worker to start writes them to the store, the rest are
   no-ops (publishing never clobbers a record already there).
3. **Claim → run → release.** A worker only claims a task whose dependencies are
   `done`, re-checks it's still pending after winning the lease, runs it via the
   normal agent path, and records the result back.
4. **Crash safety.** Leases carry a TTL. If a worker dies mid-task, its lease
   expires and another worker reclaims the job — and a background **heartbeat**
   renews the lease while a long task is still running, so it isn't reclaimed
   out from under a healthy worker.

## The core call

```python
from ormica import Ormica
from ormica.mycelium import Mycelium, SqliteBackend

org = Ormica("Distributed Colony", memory=Mycelium(backend=SqliteBackend("colony.db")))
# ... enqueue tasks (org.task / Task with stable ids) ...
org.run_worker(brain=brain, worker_id="worker-3")   # run this in every process
```

See [`docs/guides/distributed-execution.md`](../../docs/guides/distributed-execution.md)
for the full guide.
