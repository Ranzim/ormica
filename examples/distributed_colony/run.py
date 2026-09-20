"""Ormica Distributed Colony — one colony, many worker processes, no dispatcher.

Several OS processes point at the *same* SQLite colony file and each becomes a
worker. There is no coordinator handing out work: every worker runs the same
loop — reload the shared queue, find a runnable job, win an exclusive **lease**
on it, run it, checkpoint the result — so the jobs get split with no double
execution. Coordination lives entirely in the shared substrate (the mycelium),
the same stigmergic principle behind pheromone signals, applied to compute.

The demo is offline and deterministic (a MockBrain "computes" each answer), so
no API key is needed — but the cross-process coordination is real: it relies on
``SqliteBackend``'s atomic ``claim`` (a transactional lease), which is exactly
how separate machines would coordinate over a shared database.

Run it::

    python examples/distributed_colony/run.py
    python examples/distributed_colony/run.py --workers 6 --jobs 40 --work-ms 40

Each job simulates ``--work-ms`` of work, so with W workers the wall-clock time
drops toward ``jobs * work_ms / W`` — the speedup is printed at the end.
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import re
import tempfile
import time

from ormica import Ormica, Task
from ormica.brain import MockBrain
from ormica.mycelium import Mycelium, SqliteBackend


def _jobs(n: int) -> list[tuple[str, str]]:
    """The shared job manifest — the same for every worker (id is stable)."""
    return [(f"job-{i:02d}", f"Compute the square of {i}.") for i in range(n)]


def _make_org(db_path: str, n_jobs: int) -> Ormica:
    """A colony backed by the shared SQLite file, pre-loaded with the manifest.

    Every process builds the identical queue with **stable job ids**; the first
    worker to start publishes them to the shared store and the rest are no-ops
    (publishing is idempotent — it never clobbers a record already there).
    """
    org = Ormica("Distributed Colony", memory=Mycelium(backend=SqliteBackend(db_path)))
    org._tasks = [Task(description=q, id=jid) for jid, q in _jobs(n_jobs)]
    return org


def _brain(worker_id: str, work_ms: int) -> MockBrain:
    """A mock 'analyst' that simulates work and stamps who did it."""

    def reply(messages) -> str:
        text = messages[-1].content
        time.sleep(work_ms / 1000.0)  # stand in for real model / tool latency
        m = re.search(r"square of (\d+)", text)
        value = int(m.group(1)) ** 2 if m else -1
        return f"{value} (by {worker_id})"

    return MockBrain(reply_fn=reply)


def worker_main(db_path: str, n_jobs: int, worker_id: str, work_ms: int) -> None:
    """Entry point for one worker process: join the colony and drain the queue."""
    org = _make_org(db_path, n_jobs)
    tally = org.run_worker(
        brain=_brain(worker_id, work_ms),
        worker_id=worker_id,
        idle_rounds=20,   # linger a little so late work is picked up, not abandoned
        poll=0.02,
    )
    print(f"  {worker_id}: processed={tally.processed} succeeded={tally.succeeded}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ormica distributed colony demo")
    ap.add_argument("--workers", type=int, default=4, help="worker processes")
    ap.add_argument("--jobs", type=int, default=20, help="jobs in the queue")
    ap.add_argument("--work-ms", type=int, default=50, help="simulated work per job")
    ap.add_argument("--db", default=None, help="shared colony db (default: temp file)")
    args = ap.parse_args(argv)

    db = args.db or os.path.join(tempfile.mkdtemp(prefix="ormica-colony-"), "colony.db")
    print(f"colony db : {db}")
    print(f"jobs      : {args.jobs}")
    print(f"workers   : {args.workers}  (separate processes)\n")

    ctx = mp.get_context("spawn")  # portable: children re-import this module cleanly
    procs = [
        ctx.Process(target=worker_main, args=(db, args.jobs, f"worker-{k}", args.work_ms))
        for k in range(args.workers)
    ]
    t0 = time.time()
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    elapsed = time.time() - t0

    # Read the final state straight from the shared store.
    report = _make_org(db, args.jobs)
    tasks = sorted(report.load_tasks(), key=lambda t: t.id)
    done = sum(1 for t in tasks if t.status == "done")

    print(f"\n{done}/{len(tasks)} jobs done in {elapsed:.2f}s")
    for t in tasks:
        print(f"  {t.id}  {t.status:7}  {t.result}")

    # Who did what — proof the work was split, each job run exactly once.
    by_worker: dict[str, int] = {}
    for t in tasks:
        if t.result and "(by " in t.result:
            wid = t.result.split("(by ", 1)[1].rstrip(")")
            by_worker[wid] = by_worker.get(wid, 0) + 1
    print("\nsplit:", ", ".join(f"{w}={c}" for w, c in sorted(by_worker.items())))

    serial = args.jobs * args.work_ms / 1000.0
    if elapsed > 0:
        print(f"serial ≈ {serial:.2f}s  →  ~{serial / elapsed:.1f}x with {args.workers} workers")
    return 0 if done == len(tasks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
