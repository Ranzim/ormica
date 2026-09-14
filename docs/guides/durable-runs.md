# Durable, resumable runs

A complex run can process many tasks over a long time. If the process dies
partway through, you don't want to lose the finished work or re-do it. Ormica
checkpoints every task to the mycelium as it goes, so a fresh process can
**resume** — skipping what's done and re-running only what didn't finish.

## How it works

Two things make a run durable:

1. **Up-front checkpoint** — when a run starts, every queued task is written to
   `tasks/{id}` immediately (not just when it finishes). So a task that never
   got its turn is still recorded as `pending`.
2. **State transitions are persisted** — each task's record is updated to
   `running` when it starts and `done`/`failed` when it ends.

`resume()` reloads those records and re-runs whatever didn't reach `done`.

```
run starts ─► checkpoint whole queue (all pending)
each task  ─► running ─► done | failed   (each state persisted)
crash      ─► records survive on the backend
resume     ─► reload; skip done; running→pending; re-run the rest
```

## Requirements

Durability across a restart needs a **persistent backend** — SQLite or a file:

```python
from ormica import Ormica

org = Ormica("Acme", memory_db="./colony.db")   # or memory_path="./colony.json"
```

With the default in-memory backend, resume only works within the same process
(nothing survives exit).

## Resuming

In a fresh process, point at the same store and call `resume`:

```python
org = Ormica("Acme", memory_db="./colony.db")
org.resume(brain=ClaudeBrain())
```

- `done` tasks are **skipped**.
- Tasks interrupted mid-flight (`running`) are reset to `pending` and re-run.
- `failed` tasks are skipped by default; pass `retry_failed=True` to re-run them.

`resume()` accepts the same keyword arguments as `run()` (`max_tasks`,
`on_task_start`, `on_task_done`).

## Inspecting persisted tasks

`load_tasks()` rebuilds the queue from the backend without running anything —
useful to see where a run stands:

```python
for t in org.load_tasks():
    print(t.id, t.status, t.target, "→", t.result)
```

## Caveats (prototype scope)

- **Task-level, at-least-once.** Resume re-runs an interrupted task from the
  start — if a task had side effects (sent an email, opened a PR) before the
  crash, those can repeat. Make task side effects idempotent, or gate them
  behind [verification](./verification.md) / [human approvals](./human-approvals.md).
- **Tree state isn't persisted yet.** The task queue and results are durable;
  the live agent *tree* (spawned nodes) is still rebuilt from your colony
  definition. Persisting the tree is a separate follow-up.

## Pairs well with

- [Planning](./planning.md) — a decomposed plan becomes a durable queue you can resume.
- [Persistence](./persistence.md) — the backends that make this work.
