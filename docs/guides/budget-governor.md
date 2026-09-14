# Budget governor — hard ceilings on colony growth

A self-spawning colony can grow without bound — thousands of agents, each
costing tokens. Canopy's [permission chain](../architecture/04-governance.md)
decides *who approves* a spawn; the **budget governor** decides whether the
colony can *afford* one at all. It's the economic ceiling that keeps "one agent
spawns more agents" from becoming a runaway bill.

## What it enforces

`BudgetGovernor` is an arbor `SpawnPolicy` with three independent ceilings (use
any subset):

| Ceiling | Denies a spawn when… |
|---|---|
| `max_agents` | the tree already has this many **live** nodes |
| `max_spawns` | this governor has already approved this many spawns (**cumulative** — counts even nodes later pruned) |
| `budget` + `reserve_tokens` | the shared `TokenBudget` has `remaining <= reserve_tokens` |

A denied spawn raises `SpawnDenied` (as any policy denial does); the reason is
on `governor.last_denial`.

## Install it

Pass `spawn_governor` to the org. It composes automatically — chained with any
policy you pass and wrapped by the constitution so per-node spawn rules still
cascade:

```python
from ormica import Ormica
from ormica.canopy import BudgetGovernor

org = Ormica("Acme", spawn_governor=BudgetGovernor(max_agents=50, max_spawns=200))

org.spawn("sales")   # fine
# ... once the colony hits 50 live nodes, the next spawn raises SpawnDenied
```

## Gating growth on a token budget

Share one `TokenBudget` between the org (so every agent's spend accumulates on
it) and the governor (so it stops spawning when the budget runs low):

```python
from ormica.brain import TokenBudget
from ormica.canopy import BudgetGovernor

budget = TokenBudget(limit=1_000_000)

org = Ormica(
    "Acme",
    budget=budget,                                   # agents spend against it
    spawn_governor=BudgetGovernor(budget=budget, reserve_tokens=10_000),
)
```

Now two things happen automatically:

1. **Runtime:** every task run debits `budget`; once it's exhausted, further
   tasks fail fast with `BudgetExhausted` (they don't silently overspend).
2. **Spawn-time:** once `remaining <= reserve_tokens`, the governor refuses to
   spawn new agents — no point growing a colony you can't afford to run.

`reserve_tokens` is a safety margin: stop spawning *before* the budget is bone
dry, leaving headroom for in-flight agents to finish.

## Composing with everything else

Because it's just a `SpawnPolicy`, the governor stacks with the rest of
governance:

- **Constitution spawn rules** (`block_role`, `max_depth`, per-node rules) —
  still enforced; the governor is chained as the inner policy.
- **Canopy approval chain** — pass it as the governor's `inner` (or the org's
  `policy`) so a spawn must pass *both* the economic ceiling and human/role
  approval.

## Scope note

The token ceiling is enforced per-process against the shared `TokenBudget`.
Cost in currency is `tokens × your model's price` — track that in your own code
for now; a first-class cost (USD) ceiling is a small follow-up on top of this.

## Pairs well with

- [Human approvals](./human-approvals.md) — approve high-risk spawns; the governor caps quantity.
- [Durable runs](./durable-runs.md) — a shared budget survives conceptually across a resume if you persist and restore its `used`.
