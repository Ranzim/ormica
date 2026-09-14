# Planning — decompose a complex goal into runnable tasks

> **Opt-in — a top-down alternative to emergent growth.** Ormica's default model
> is *emergent*: you define goals and the colony grows its own tree by spawning —
> "no fixed graphs, no predefined chains" (see the
> [philosophy](../../README.md)). The planner is the deliberate opposite:
> explicit, up-front decomposition into a fixed DAG. Reach for it when you want a
> plan you can **inspect and approve before it runs** — auditability, compliance,
> cost estimation — rather than trusting emergence. It's an optional layer, off
> unless you call `org.plan(...)`.

The **planner** takes a goal and a brain, asks the brain to break the goal into
concrete subtasks — with routing and dependencies — then turns that into runnable
`Task`s in the right order.

## Quick start

```python
from ormica import Ormica
from ormica.brain import ClaudeBrain

org = Ormica("Acme")
org.plant("business")

plan = org.plan("Launch the Q3 newsletter", brain=ClaudeBrain(), max_depth=2)
print(plan.pretty())          # inspect before running

org.enqueue_plan(plan)         # add the plan's leaves to the queue
org.run(brain=ClaudeBrain())   # execute in dependency order
```

`org.plan(...)` only *builds* the plan — nothing is enqueued until you call
`enqueue_plan`, so you can inspect or edit it first.

## What a plan looks like

`Plan` is a tree of `PlannedStep`s. Each step has a `description`, an optional
`target` (which department/node runs it), an optional `priority`, and
`depends_on` (sibling steps that must finish first). Recursively decomposed
steps carry `substeps`; the **leaves** are the actual work.

```
Goal: Launch the Q3 newsletter
  - Research target audience @marketing
  - Draft the newsletter @marketing (after 1)
  - Review for compliance @legal (after 1)
  - Schedule and send (after 1)
```

## Dependencies and ordering

The brain expresses dependencies as **1-based indices** into the step list
(easy for a model to get right); the planner maps them to stable step ids and
topologically sorts:

```python
tasks = plan.to_tasks()   # leaves, dependency-respecting order
# -> Task("Research...") , Task("Draft...") , Task("Review...") , Task("Schedule...")
```

A dependency cycle or a reference to a non-existent step raises `PlanError`.

> Ordering is currently enforced by *sequence* — the sequential runner executes
> tasks in the order `to_tasks()` returns. True parallel dependency scheduling
> (run independent branches concurrently, block only on real prerequisites) is a
> runner-level follow-up.

## Recursive decomposition

`max_depth` controls how many levels deep the planner breaks the goal down.
`max_depth=1` (default) is a single flat level; higher values re-decompose each
step until the model returns a single step (treated as atomic) or the depth
limit is reached:

```python
plan = org.plan("Rebuild the billing system", brain=brain, max_depth=3)
```

## Routing to departments

Pass `targets` so the planner routes each subtask to a real department:

```python
plan = org.plan(
    "Handle the enterprise onboarding",
    brain=brain,
    targets=["sales", "engineering", "support"],
)
```

## Using the planner directly

Without the facade:

```python
from ormica.planner import Planner

plan = Planner(brain).plan("goal", targets=["a", "b"], max_depth=2)
for task in plan.to_tasks():
    ...  # feed to your own runner
```

`AsyncPlanner` is the awaitable sibling for use with async brains.

## Pairs well with

- [Verification](./verification.md) — decompose *and* verify each subtask's output.
- [Semantic memory](./semantic-memory.md) — subtasks share findings through the mycelium.
- [Async & routing](./async-and-routing.md) — run the resulting tasks concurrently.
