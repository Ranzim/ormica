# Benchmarks

Offline, deterministic benchmarks (a `MockBrain`, no API keys) that measure the
**engine** — not the model. Run the suite:

```bash
python benchmarks/bench.py                        # all, default sizes
python benchmarks/bench.py --tasks 5000
python benchmarks/bench.py --only distributed --workers 8
```

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

| Benchmark | Result |
|---|---|
| Sync throughput | ~100k trivial tasks/sec |
| Caching (90% repeat) | **~9× faster** end-to-end; hit-rate 90% |
| Distributed (400 tiny jobs) | ~1.8× on 4 workers* |
| Memory | ~480 bytes/node (10k nodes ≈ 5 MB) |

\* Trivial jobs are **coordination-bound** — the SQLite lease overhead dominates
when each job is near-zero work. Real LLM tasks (seconds each) parallelise close
to linearly; this number is the pessimistic floor, not the ceiling.

## Notes for interpreting results

- `run()` / `arun()` default to `max_tasks=100`; the benchmarks pass `max_tasks`
  explicitly so the full queue runs.
- The distributed benchmark spawns real OS processes over a shared `SqliteBackend`
  — the same path a multi-machine deployment uses.
