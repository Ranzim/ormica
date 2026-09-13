# Parallel, DAG-aware execution

The planner turns a goal into subtasks with dependencies. The default runners
execute a queue in order; `arun_dag` instead runs that dependency graph with
**maximum safe parallelism** — a task starts the moment its prerequisites are
done, and independent branches run concurrently.

## Dependencies on a Task

Every `Task` has a `depends_on` list of task ids that must reach `done` first:

```python
from ormica import Task

a = Task(description="fetch data", id="a")
b = Task(description="analyze", id="b", depends_on=["a"])
```

The planner sets these for you — `plan.to_tasks()` translates each step's
dependencies (and any inherited from ancestor steps) into leaf task ids.

## Running a DAG

```python
plan = org.plan("Research the market and write a brief", brain=brain, max_depth=2)
org.enqueue_plan(plan)          # tasks carry the plan's dependencies
await org.arun_dag(brain=brain, concurrency=5)
```

Semantics:

- A task runs only after **all** tasks in its `depends_on` are `done`.
- Independent tasks run **concurrently**, capped by `concurrency`.
- Among ready tasks, higher `priority` goes first.
- A **dependency cycle** raises `ValueError` before anything runs.

### A diamond

```
        a
       / \
      b   c        # b and c run in parallel after a
       \ /
        d          # d runs after both b and c
```

```python
org._tasks = [
    Task(description="fetch",     id="a"),
    Task(description="analyze-1", id="b", depends_on=["a"]),
    Task(description="analyze-2", id="c", depends_on=["a"]),
    Task(description="report",    id="d", depends_on=["b", "c"]),
]
await org.arun_dag(brain=brain, concurrency=4)
# a, then b+c together, then d — faster than running all four in sequence.
```

## Failure blocks the downstream, not the siblings

If a task fails, every task **downstream** of it is skipped (marked `failed`
with a `"prerequisite … failed"` reason) rather than run against a missing
input. Independent branches are unaffected and still run.

```
a (fails) ─► b   →  b is skipped
c            →  c runs normally (independent of a)
```

## Durability

`arun_dag` checkpoints like the other runners, and `depends_on` is persisted in
each task record — so a DAG run is [resumable](./durable-runs.md): `resume()`
reloads the graph and re-runs only what didn't finish.

## Scope note

This is single-process parallelism (`asyncio`), the same model as `arun`. It's
the on-ramp to distributed execution — the scheduler already thinks in terms of
"ready tasks" and a concurrency budget, which a multi-worker backend would slot
into.

## Pairs well with

- [Planning](./planning.md) — produces the DAG this runs.
- [Durable runs](./durable-runs.md) — resume an interrupted DAG.
- [Async & routing](./async-and-routing.md) — the async brain/runner foundation.
