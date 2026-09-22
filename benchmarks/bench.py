"""Ormica benchmarks — real numbers for throughput, scaling, caching, memory.

Offline and deterministic (a `MockBrain`, no API keys), so it measures the
*engine*, not the model. Run the whole suite or one benchmark:

    python benchmarks/bench.py                 # all, default sizes
    python benchmarks/bench.py --tasks 5000    # bigger throughput run
    python benchmarks/bench.py --only distributed --workers 8

What it measures:
  • throughput   — tasks/sec through the sync + async runners
  • caching      — CachingBrain hit-rate and the wall-clock it saves
  • distributed  — N worker processes over one shared SQLite queue (speedup)
  • memory       — peak allocation growing a colony to M nodes
"""
from __future__ import annotations

import argparse
import asyncio
import multiprocessing as mp
import os
import tempfile
import time
import tracemalloc

from ormica import Ormica, Task
from ormica.brain import AsyncMockBrain, CachingBrain, MockBrain
from ormica.mycelium import Mycelium, SqliteBackend


def _row(label: str, **cols) -> None:
    parts = "  ".join(f"{k}={v}" for k, v in cols.items())
    print(f"  {label:<22} {parts}")


# --- throughput ---------------------------------------------------------------


def bench_throughput(n: int) -> None:
    print(f"\nThroughput — {n} trivial tasks (in-memory backend)")

    org = Ormica("bench")
    org.spawn("w", role="w")
    for i in range(n):
        org.task(f"task {i}", target="w")
    brain = MockBrain(reply_fn=lambda m: "ok")
    t0 = time.perf_counter()
    res = org.run(brain=brain, max_tasks=n)
    dt = time.perf_counter() - t0
    _row("sync run", tasks=n, seconds=f"{dt:.3f}", per_sec=f"{n / dt:,.0f}", ok=res.succeeded)

    org2 = Ormica("bench")
    for i in range(n):
        org2.task(f"task {i}")

    async def areply(_m):
        return "ok"

    t0 = time.perf_counter()
    asyncio.run(org2.arun(brain=AsyncMockBrain(reply_fn=areply), concurrency=16, max_tasks=n))
    dt = time.perf_counter() - t0
    _row("async run (c=16)", tasks=n, seconds=f"{dt:.3f}", per_sec=f"{n / dt:,.0f}")


# --- caching ------------------------------------------------------------------


def bench_caching(n: int, unique: int, work_ms: int = 2) -> None:
    print(f"\nCaching — {n} tasks, {unique} distinct prompts, {work_ms}ms 'model' latency")

    def slow(messages):
        time.sleep(work_ms / 1000.0)
        return "answer"

    for cached in (False, True):
        org = Ormica("bench")
        for i in range(n):
            org.task(f"question {i % unique}")   # only `unique` distinct prompts
        base = MockBrain(reply_fn=slow)
        brain = CachingBrain(base) if cached else base
        t0 = time.perf_counter()
        org.run(brain=brain, max_tasks=n)
        dt = time.perf_counter() - t0
        if cached:
            _row("with cache", seconds=f"{dt:.3f}", hits=brain.hits, misses=brain.misses)
        else:
            _row("no cache", seconds=f"{dt:.3f}")


# --- distributed --------------------------------------------------------------


def _worker(db_path: str, n_jobs: int, worker_id: str) -> None:
    org = Ormica("bench", memory=Mycelium(backend=SqliteBackend(db_path)))
    org._tasks = [Task(description=f"job-{i}", id=f"job-{i:05d}") for i in range(n_jobs)]
    org.run_worker(brain=MockBrain(reply_fn=lambda m: "ok"),
                   worker_id=worker_id, idle_rounds=25, poll=0.005)


def bench_distributed(n: int, workers: int) -> None:
    print(f"\nDistributed — {n} jobs across worker processes (shared SQLite)")
    ctx = mp.get_context("spawn")
    for w in (1, workers):
        db = os.path.join(tempfile.mkdtemp(prefix="ormica-bench-"), "colony.db")
        procs = [ctx.Process(target=_worker, args=(db, n, f"w{k}")) for k in range(w)]
        t0 = time.perf_counter()
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        dt = time.perf_counter() - t0
        org = Ormica("bench", memory=Mycelium(backend=SqliteBackend(db)))
        done = sum(1 for t in org.load_tasks() if t.status == "done")
        _row(f"{w} worker(s)", jobs=n, done=done, seconds=f"{dt:.3f}", per_sec=f"{n / dt:,.0f}")


# --- memory -------------------------------------------------------------------


def bench_memory(nodes: int) -> None:
    print(f"\nMemory — growing a colony to {nodes:,} nodes")
    tracemalloc.start()
    org = Ormica("bench", max_depth=64)
    parent = org.root
    for i in range(nodes):
        parent = org.spawn(f"n{i}", under=parent if i % 8 else org.root, role="w")
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    _row("grown", nodes=len(org), peak_mb=f"{peak / 1e6:.1f}",
         bytes_per_node=f"{peak / max(1, len(org)):,.0f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ormica benchmarks")
    ap.add_argument("--only", choices=["throughput", "caching", "distributed", "memory"],
                    help="run just one benchmark")
    ap.add_argument("--tasks", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--nodes", type=int, default=5000)
    args = ap.parse_args(argv)

    print(f"Ormica benchmarks — python {os.sys.version.split()[0]}")
    run = args.only
    if run in (None, "throughput"):
        bench_throughput(args.tasks)
    if run in (None, "caching"):
        bench_caching(args.tasks, unique=max(1, args.tasks // 10))
    if run in (None, "distributed"):
        bench_distributed(min(args.tasks, 400), args.workers)
    if run in (None, "memory"):
        bench_memory(args.nodes)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
