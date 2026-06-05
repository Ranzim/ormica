# Pillar 3 — Constitutional Governance

**Module:** `cortex`
**Solves:** the "agent does what you didn't ask for" problem. Hard constraints and soft policies that govern agent behavior, independent of which Brain generates the response.

## What it is

The pitch puts it bluntly:

> *Cortex is the "Law of the Colony." Developers encode their business values and hard constraints (the Constitution) into the engine's core. This ensures that even as agents act autonomously, they never violate safety boundaries or business logic.*

Anatomically, the cerebral cortex is the part of the brain that **inhibits impulses generated lower down**. Ormica mirrors that exactly: **`brain` generates, `cortex` enforces**.

## The three primitives

| Type | Where | Role |
|---|---|---|
| `Rule` | [`ormica/cortex/rule.py`](../../ormica/cortex/rule.py) | One predicate over a context dict. Has `stage` + `severity`. |
| `Constitution` | [`ormica/cortex/constitution.py`](../../ormica/cortex/constitution.py) | Collection of rules; `check` returns violations, `enforce` raises on hard ones. |
| `ConstitutionPolicy` | [`ormica/cortex/policy.py`](../../ormica/cortex/policy.py) | Wraps a Constitution as an arbor `SpawnPolicy` — also governs tree growth. |

## A Rule

```python
from ormica.cortex import Rule

no_finance_at_night = Rule(
    name="no_finance_at_night",
    description="finance agents may not act on after-hours prompts",
    check=lambda ctx: not (ctx["role"] == "finance" and "after-hours" in ctx["prompt"]),
    stage="pre",          # "pre" | "post" | "spawn"
    severity="hard",      # "hard" raises RuleViolation; "soft" emits only
)
```

- `stage="pre"` runs before any `brain.think` call.
- `stage="post"` runs after, with the result in the context. *(seam exposed; integration in a follow-up.)*
- `stage="spawn"` runs only on tree growth (via `ConstitutionPolicy`).

The `check` callable receives a context dict prepared by Ormica. Currently:

| Stage | Context keys |
|---|---|
| `pre` | `node` · `role` · `task` · `prompt` · `budget` |
| `spawn` | `parent` · `child_name` · `depth` |

If a rule's `check` raises, the exception is wrapped into a `Violation` — rules never crash the run.

## A Constitution

```python
from ormica.cortex import Constitution, Rule, RuleViolation

constitution = Constitution([
    Rule(
        name="max_spend",
        description="total tokens used must be < 100k",
        check=lambda ctx: ctx["budget"] is None or ctx["budget"].used < 100_000,
    ),
    Rule(
        name="depth_cap",
        description="don't grow past depth 4",
        check=lambda ctx: ctx["depth"] <= 4,
        stage="spawn",
    ),
])

violations = constitution.check(context, stage="pre")    # → list[Violation]
constitution.enforce(context, stage="pre")               # raises RuleViolation if any hard rule failed
```

`enforce` raises `RuleViolation` (with the full list of failed hard rules) when any hard rule fails; soft violations are returned for the caller to log.

## Wiring into Ormica

```python
from ormica import Ormica
from ormica.cortex import Constitution, Rule

org = Ormica("Acme", constitution=Constitution([
    Rule(name="no_finance", description="block finance role",
         check=lambda ctx: ctx["role"] != "finance"),
]))

org.plant("business")
org.task("any task", dept="finance")
org.run(brain=...)
# → finance task is marked failed with error: "RuleViolation: no_finance: ..."
```

When `constitution=` is passed to `Ormica(...)`:
1. The Constitution is stored on the facade (`org.constitution`).
2. The Constitution is *also* wrapped as a `ConstitutionPolicy` and composed with whatever `SpawnPolicy` you passed via `policy=`. So spawn-stage rules govern tree growth automatically.
3. Every runner-built `Agent` is constructed with `constitution=org.constitution`, so `pre`-stage rules fire before each `Brain.think` call.

## Composition with canopy

`ConstitutionPolicy` accepts an `inner=` policy and short-circuits: if its constitution denies, the answer is no; otherwise it delegates to `inner`. So:

```python
canopy = Canopy(...)
policy = ConstitutionPolicy(constitution, inner=canopy)
org = Ormica("Acme", policy=policy)
```

…enforces *both* (a) the constitution's `spawn`-stage rules, and (b) canopy's AUTO/CHAIN/ROOT permission chain. Either can deny.

## Hard vs soft

| Severity | Effect on agent run | Use case |
|---|---|---|
| `hard` | Raises `RuleViolation`. The task is marked `failed`; the run continues. | Token budgets, role-specific blocks, safety constraints. |
| `soft` | Emits a violation; the action proceeds. | Tracking + analytics; "flag but allow". |

Soft rules are returned from `enforce()` so the caller can route them into observability (a future `RuleEvent` is a clean follow-up).

## What's deliberately *not* in this module

- **No DSL for rules.** Rules are plain Python callables. If you want YAML/JSON rules, build a loader that returns `Rule` objects.
- **No rule engine / inference.** Rules don't reference each other; each evaluates independently.
- **No post-stage automatic wiring yet.** The `post` stage exists on `Rule`; runners don't call it yet because no current use case demands it. Easy to add when one appears.
- **No per-node constitution.** One Constitution per `Ormica`. Per-node rules can be encoded by branching on `ctx["node"]` inside a Rule's `check`.

## Related

- [Pillar 1 — Hierarchy](./01-hierarchy.md) — canopy and ConstitutionPolicy compose at the SpawnPolicy seam.
- [Writing a Constitution](../guides/writing-a-constitution.md) — patterns for real-world rules.
- [Pillar 4 — Observability](./05-observability.md) — failed tasks (including rule violations) land in the Thought Trail.
