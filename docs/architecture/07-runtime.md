# Runtime — Agent · Task · Runner

**Files:** [`ormica/agent.py`](../../ormica/agent.py) · [`ormica/runtime.py`](../../ormica/runtime.py)
**Role:** turn nodes into thinking entities, queue them work, and drive the work — sync or async.

## Agent — Node + Brain

`Agent` is the bridge. It pairs an `arbor.Node` with a `brain.Brain` and (optionally) memory, signals, a token budget, a constitution, and observability hooks.

```python
from ormica import Agent
from ormica.brain import ClaudeBrain

agent = Agent(
    node,                             # from Tree.spawn
    brain=ClaudeBrain(),
    memory=org.memory,                # optional Mycelium
    signals=org.signals,              # optional Stigma
    budget=TokenBudget(limit=10_000), # optional cap
    constitution=org.constitution,    # optional governance
    system_prompt="be concise",       # optional override
)

response = agent.act("Summarize the latest pull requests")
```

`AsyncAgent` is the same surface with `async def act(...)`. Both share a `_AgentBase` mixin so memory/signal/budget logic isn't duplicated.

### What `act()` does, in order

1. **Budget check** — raise `BudgetExhausted` if the token cap is hit.
2. **Constitution enforce** — run `pre`-stage rules; raise `RuleViolation` if any hard rule fails.
3. **Compose system prompt** — explicit kwarg ▸ template prompt (from `node.meta`) ▸ `Your role: ...` ▸ `Your task: ...`.
4. **Mark node `WORKING`.**
5. **Call `brain.think(...)`.**
6. **Emit `think.recorded`** to the org's event bus (for the Thought Trail).
7. **Mark node `DONE`** (or `FAILED` on exception).
8. **Consume budget tokens.**
9. **Return the Response.**

### Tool-use loop

`act_with_tools(prompt, tools=[...], max_iterations=8)` is the multi-turn loop:

```
think → if response.wants_tools:
            execute each tool, append tool_result messages
            loop again
        else:
            return final response
```

Hits `max_iterations` without resolving → `ToolLoopExceeded`. Unknown tool names land as error messages (not crashes). Tool exceptions land as error tool_result messages — the model can recover. See [Writing tools](../guides/writing-tools.md).

## Task — one unit of work

```python
from ormica.runtime import Task

t = Task(description="Reach out to 3 SMB leads", target="sales", priority="high")
```

| Field | Meaning |
|---|---|
| `description` | What to do (becomes the user prompt) |
| `target` | Node name to route to. Empty = root. |
| `priority` | `high` / `normal` / `low` |
| `id` | Auto-generated 8-char hex |
| `status` | `pending` → `running` → `done` / `failed` |
| `result` | Final response content if done |
| `error` | Exception text if failed |

The Ormica facade exposes a sugar method:

```python
org.task("Reach out to 3 SMB leads", dept="sales", priority="high")
# dept= is an alias for target=
```

## TaskRunner — sync drain

```python
runner = TaskRunner(org, brain=ClaudeBrain(), max_tasks=100)
result = runner.run(org.pending_tasks())
# RunResult(processed=N, succeeded=N, failed=N)
```

**Priority-then-FIFO scheduling.** `high` tasks first, then `normal`, then `low`; ties broken by creation time. Failures (resolution errors, brain exceptions, budget exhaustion, rule violations) mark the task `failed` and the loop **continues** — one bad task ≠ a dead run.

The same `cortex` / `brain` selection logic supports a `Router` instead of a bare `Brain`:

```python
runner = TaskRunner(org, brain=router)    # per-node brain selection
```

## AsyncTaskRunner — concurrent drain

```python
runner = AsyncTaskRunner(org, brain=AsyncClaudeBrain(), concurrency=5)
await runner.run(org.pending_tasks())
```

**Priority bands run sequentially; within a band, tasks fan out concurrently** (capped by `concurrency` via an `asyncio.Semaphore`). So a queued `high` task blocks a `normal` from starting, but two `normal` tasks race freely.

Tested in [`tests/test_async_runtime.py`](../../tests/test_async_runtime.py).

## Lifecycle events emitted per task

| Event | Payload (selected) |
|---|---|
| `run.started` | `n_tasks` · `mode` · `concurrency` |
| `task.started` | `task_id` · `target` · `priority` · `description` |
| `think.recorded` | `task_id` · `node_id` · `messages` · `tool_names` · `response_content` · `tokens_used` |
| `task.done` | `task_id` · `target` · `tokens_used` |
| `task.failed` | `task_id` · `target` · `error` |
| `run.completed` | `processed` · `succeeded` · `failed` |

A `TraceObserver` aggregates these into per-task `Trace` objects ([Pillar 4](./05-observability.md)).

## Persistence side-effect

Every task's outcome lands in mycelium under `tasks/{task_id}`:

```python
org.read("tasks/abc12345").value
# → {"id": ..., "description": ..., "target": ..., "priority": ..., "status": "done", "result": "...", "error": None}
```

Pair with `SqliteBackend` and you have task history across process restarts.

## Related

- [Pillar 3 — Governance](./04-governance.md) — Constitution enforcement happens inside `Agent.act`.
- [Pillar 4 — Observability](./05-observability.md) — every think call emits an event.
- [Async + Router](../guides/async-and-routing.md) — the parallelism story.
- [Brain](./03-brain.md) — what `brain.think` actually does.
