# Benchmarks

Offline, deterministic benchmarks (a `MockBrain`, no API keys) that measure the
**engine** — not the model. Run the suite:

```bash
python benchmarks/bench.py                        # all, default sizes
python benchmarks/bench.py --tasks 5000
python benchmarks/bench.py --only distributed --workers 8
python benchmarks/bench.py --tasks 200 --latency-ms 20   # realistic model latency
```

**`--latency-ms`** makes the MockBrain sleep to *simulate* a real model — free,
deterministic, no keys. This is the right way to see how async concurrency,
distributed workers, and caching help under real conditions. (A real brain is
wrong for benchmarks: it measures the model + network, not the engine, and hits
rate limits. Use `MockBrain` here; keep real-model runs to the examples.)

## What it measures

| Benchmark | Question it answers |
|---|---|
| **throughput** | How many trivial tasks/sec through the sync + async runners? |
| **caching** | How much does `CachingBrain` save when prompts repeat? |
| **distributed** | Do worker processes over one shared SQLite queue scale? |
| **memory** | How much RAM does a large colony cost? |

## Indicative numbers

Offline, `MockBrain`, one dev laptop (Python 3.14) — **your mileage varies**; these
measure engine overhead, so real runs are dominated by model latency, not this.

**Engine-only** (trivial tasks, no latency — pure overhead):

| Benchmark | Result |
|---|---|
| Sync throughput | ~100k trivial tasks/sec |
| Memory | ~480 bytes/node (10k nodes ≈ 5 MB) |

**Realistic** (`--latency-ms 20`, 200 tasks — where the parallelism shows):

| Benchmark | Result |
|---|---|
| Async runner (c=16) | **~14× faster** than serial |
| Caching (90% repeat) | **~10× faster**; 90% hit-rate |
| Distributed (4 workers) | **~3.8× — near-linear** |

The distributed number is coordination-bound *only* when jobs are near-zero work
(≈1.8× on 400 trivial jobs); give each job real latency and it scales close to
linearly — the honest floor and ceiling.

## Notes for interpreting results

- `run()` / `arun()` default to `max_tasks=100`; the benchmarks pass `max_tasks`
  explicitly so the full queue runs.
- The distributed benchmark spawns real OS processes over a shared `SqliteBackend`
  — the same path a multi-machine deployment uses.
