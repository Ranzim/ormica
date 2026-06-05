# Async runs and multi-provider routing

Fan out tasks concurrently, optionally with different brains per node.

## The sync baseline

```python
from ormica import Ormica
from ormica.brain import ClaudeBrain

org = Ormica("Acme")
org.plant("business")
for dept in ("operations", "sales", "marketing", "finance"):
    org.task(f"do {dept} work", dept=dept)

org.run(brain=ClaudeBrain())
# Tasks processed one at a time. 4 tasks × 300ms each ≈ 1.2s.
```

## Going async

Switch `run` → `arun`, `ClaudeBrain` → `AsyncClaudeBrain`, and you get **concurrent execution within each priority band**:

```python
import asyncio
from ormica.brain import AsyncClaudeBrain

result = asyncio.run(
    org.arun(brain=AsyncClaudeBrain(), concurrency=5)
)
# 4 tasks × 300ms each ≈ 0.3s.
```

What changes:
- `org.arun` is awaitable; wrap with `asyncio.run` from sync code or `await` directly inside an async function.
- The runner builds `AsyncAgent` instead of `Agent`.
- `asyncio.Semaphore(concurrency)` caps how many tasks run in parallel.

## Priority bands stay sequential

The runner still respects priority:

```
high (3 tasks)  →  await asyncio.gather(...)  →  done
                                                 ↓
normal (5 tasks) → await asyncio.gather(...) →  done
                                                 ↓
low (2 tasks)    → await asyncio.gather(...) →  done
```

So a queued `high` task **blocks a normal one from starting** — but two `normal` tasks race freely. This is the design from [`tests/test_async_runtime.py::test_arun_priority_bands_run_sequentially`](../../tests/test_async_runtime.py).

## CLI version

```bash
ormica run --async --concurrency 5
```

Identical effect, no Python required. Use it for batch runs from cron / CI.

## Mixed-provider routing

Use a `Router` to give different nodes different brains:

```python
from ormica.brain import AsyncClaudeBrain, AsyncGPTBrain, Router

router = Router(
    default=AsyncGPTBrain(model="gpt-4o-mini"),           # cheap default
    by_role={
        "executive": AsyncClaudeBrain(model="claude-opus-4-7"),  # smart leadership
        "finance":   AsyncClaudeBrain(model="claude-opus-4-7"),  # smart finance
    },
    by_name={
        "scout-7": AsyncGPTBrain(model="gpt-4o-mini"),    # node-specific override
    },
)

await org.arun(brain=router, concurrency=10)
```

Resolution order: **name → role → default**. The `Router` doesn't care about sync vs async — it just returns whatever you stored. Mixing `Brain` + `AsyncBrain` in one Router works at runtime; but make sure the runner matches (`run` vs `arun`).

## When to go async

| Use case | Sync (`run`) | Async (`arun`) |
|---|---|---|
| 1–3 tasks total | ✅ simpler | overkill |
| 10+ tasks, single provider | ⚠️ slow | ✅ |
| Need to fan out to multiple providers | hard | ✅ Router + arun |
| CI / batch / nightly | either | ✅ `ormica run --async` |
| Interactive REPL / single-shot demos | ✅ | overhead |

## Concurrency tuning

`concurrency=5` is a safe default. Tune based on:
- **Provider rate limits.** Hitting 429s? Drop concurrency.
- **Cost ceiling.** More concurrency = more spend per minute, same spend per task.
- **Memory & file-handle limits.** Each in-flight task holds a `Brain` reference and any tools.

There's no rate-limit handling inside Ormica — the Anthropic / OpenAI SDKs retry on their own. If you need application-level throttling, wrap the brain (a future `RateLimitedAsyncBrain` would be a tiny adapter).

## Common pitfalls

### Routing a `Brain` (sync) through `arun` (async)
```python
# WRONG
router = Router(default=ClaudeBrain())     # sync brain
await org.arun(brain=router)               # async runner
# → TypeError when the runner awaits brain.think(...)
```
Use `AsyncClaudeBrain` for async runs.

### Forgetting `concurrency=`
The default is 5. If your provider's rate limit is lower (say, 2 concurrent requests), set it explicitly.

### Mixing tool execution with `asyncio`
`Tool` functions are sync. If your tool blocks for seconds (e.g., a DB query), it blocks the event loop. Wrap with `loop.run_in_executor(...)` inside the tool, or move tools to background workers.

## Related

- [Runtime architecture](../architecture/07-runtime.md) — what the runner does.
- [Brain](../architecture/03-brain.md) — sync vs async adapters.
- [Pillar 4 — Observability](../architecture/05-observability.md) — observers see async events the same as sync.
