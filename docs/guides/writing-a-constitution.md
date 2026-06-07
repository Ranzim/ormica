# Writing a Constitution

Encode the colony's law — hard constraints and soft policies that govern what agents may do.

## The minimal rule

```python
from ormica.cortex import Rule

depth_cap = Rule(
    name="depth_cap",
    description="Don't grow the tree past depth 4",
    check=lambda ctx: ctx["depth"] <= 4,
    stage="spawn",
)
```

A rule is **one predicate**. It takes a context dict, returns `True` if the action is allowed. The context's contents depend on the stage.

## When rules run

| `stage` | When | Context includes | Typical use |
|---|---|---|---|
| `pre` (default) | Before each `brain.think` | `prompt`, `role`, `task`, `budget` | Block risky inputs; cap token spend |
| `post` | After a successful `brain.think` (final response only in `act_with_tools`) | pre keys + `response` | Block disallowed response content; flag patterns for analytics |
| `spawn` | Before a new node is created (`Tree.spawn`) | `parent`, `child_name`, `depth`, `role`, `task_text` | Cap tree depth; veto risky child roles |

A hard violation at any stage raises `RuleViolation`. At `pre` and `spawn` this means the action never happens. At `post` the think call has already happened (tokens were spent) but the response is blocked from being used by the caller.

## The four common patterns

### 1. Block a role from acting

```python
no_finance_after_hours = Rule(
    name="no_finance_after_hours",
    description="Finance agents can't act on after-hours prompts.",
    check=lambda ctx: not (
        ctx["role"] == "finance"
        and "after-hours" in ctx["prompt"].lower()
    ),
)
```

Default `stage="pre"` fires before every `Brain.think` call.

### 2. Cap total token spend

```python
max_spend = Rule(
    name="max_spend",
    description="Total tokens spent must stay under 100k.",
    check=lambda ctx: ctx["budget"] is None or ctx["budget"].used < 100_000,
)
```

The `TokenBudget` is exposed in the context. You can build a budget at the org level and share it across agents.

### 3. Cap tree depth

```python
no_deep_growth = Rule(
    name="depth_cap",
    description="Don't grow past depth 4.",
    check=lambda ctx: ctx["depth"] <= 4,
    stage="spawn",                              # ← runs on Tree.spawn
)
```

`stage="spawn"` context: `parent` · `child_name` · `depth`.

### 4. Block disallowed content in the response

```python
ban_secret = Rule(
    name="ban_secret_word",
    description="Responses must not mention 'secret'.",
    check=lambda ctx: "secret" not in ctx["response"].content.lower(),
    stage="post",
)
```

`stage="post"` context adds `response` to the pre-stage keys. `response.content` is the model's text; `response.tokens_used` is the call's cost. Use `severity="soft"` if you want to flag-and-allow rather than block.

### 5. Block specific agent names from spawning

```python
no_finance_clones = Rule(
    name="no_finance_clones",
    description="Only one finance node allowed.",
    check=lambda ctx: not (
        ctx["child_name"] == "finance"
        and any(n.name == "finance" for n in ctx["parent"].walk())
    ),
    stage="spawn",
)
```

## Assembling the Constitution

```python
from ormica.cortex import Constitution

constitution = Constitution([
    depth_cap,
    no_finance_after_hours,
    max_spend,
])
```

You can also `constitution.add(rule)` later — useful for plugging in domain-specific rules at runtime.

## Wiring into Ormica

```python
from ormica import Ormica

org = Ormica("Acme", constitution=constitution)
```

When `constitution=` is passed:
- It's stored as `org.constitution`.
- It's also wrapped as a `ConstitutionPolicy` and composed with any `SpawnPolicy` you supply — so `spawn`-stage rules govern tree growth.
- Every runner-built `Agent` gets `constitution=org.constitution` — `pre`-stage rules fire before every `Brain.think`.

## What happens when a rule fails

| Severity | Effect |
|---|---|
| `hard` (default) | Raises `RuleViolation`. The task is marked `failed`; the run continues. |
| `soft` | Returned from `enforce()` as a violation; the action proceeds. |

```python
soft_warn = Rule(
    name="weekend_alert",
    description="Flag spending on weekends.",
    check=lambda ctx: not (
        datetime.now().weekday() >= 5
        and ctx["budget"] is not None
        and ctx["budget"].used > 0
    ),
    severity="soft",
)
```

Soft violations don't stop the action; they're a signal for analytics.

## Composing with canopy

If you already use `Canopy` for permission, both can coexist:

```python
from ormica.canopy import Canopy, RoleRisk, RiskLevel
from ormica.cortex import ConstitutionPolicy

canopy = Canopy(assessor=RoleRisk({"finance": RiskLevel.ROOT}))
policy = ConstitutionPolicy(constitution, inner=canopy)

org = Ormica("Acme", policy=policy)
```

Now spawning a node has to pass *both* the constitution's spawn rules *and* canopy's permission chain. Either can deny.

## Best practices

- **One rule = one concern.** Don't pack multiple checks into one predicate; you lose the violation message.
- **Make `description` actionable.** It's what surfaces in `RuleViolation`. "Limit reached" is useless; "Total tokens spent must stay under 100k" is clear.
- **Lean on `severity="soft"` for "flag but allow".** Hard rules are the seatbelt; soft rules are the speedometer.
- **Test rules in isolation.** A rule is just a `check(ctx) → bool`. Unit-test it with plain dicts.

```python
def test_max_spend_blocks_when_over_limit():
    rule = Rule(name="max_spend", description="...",
                check=lambda ctx: ctx["budget"].used < 100)

    class FakeBudget:
        used = 200
    assert rule.evaluate({"budget": FakeBudget()}) is not None  # → Violation
```

## Related

- [Pillar 3 — Governance](../architecture/04-governance.md) — the architecture.
- [Pillar 1 — Hierarchy](../architecture/01-hierarchy.md) — how `SpawnPolicy` composes.
- [Reading the Thought Trail](./reading-the-thought-trail.md) — debugging which rule failed.
