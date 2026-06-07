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

## Per-node rule overrides

Rules don't have to be org-wide. Attach them to any `Node` via `node.rules` and they **cascade down the subtree**: a rule on a department applies to that department and everything under it; a rule on the root behaves like an org-wide Constitution; siblings are unaffected.

```python
org = Ormica("Acme")
sales = org.spawn("sales", role="sales")
finance = org.spawn("finance", role="finance")

# Tighter limits just for finance:
finance.rules.append(max_tokens(10_000))
finance.rules.append(banned_words({"speculative", "off-book"}))

# Stricter spawn depth just for sales:
sales.rules.append(max_depth(3))
```

What's evaluated for a node's think call:
- the org-level `Constitution` (if any), **plus**
- every rule attached to any node on the path from root to the acting node.

Per-node spawn rules read the *parent's* ancestor chain (since the child doesn't exist yet). Per-node rules work even when `Ormica(constitution=)` is not set — no need to pass an empty Constitution as a workaround.

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

## Declaring rules in YAML

Drop a `constitution:` block into `ormica.yaml` and the CLI builds the Constitution for you — no Python required for the common cases:

```yaml
name: My SaaS
industry: business
constitution:
  rules:
    - max_depth: 4
    - max_tokens: 100000
    - block_role: finance
    - banned_words: [secret, confidential]
    - require_json                # zero-arg form
```

Each entry is either a bare factory name (zero-arg) or a single-key mapping whose value becomes the factory's positional argument. Unknown names raise a clear `ValueError` listing what's available — so a typo like `max_dept` doesn't silently disable governance.

For per-node rules, the colony YAML's template entries take the same shape:

```yaml
# industries/saas.yaml
name: saas
templates:
  - name: finance
    role: finance
    rules:                                # ← attached to node.rules at plant time
      - max_tokens: 10000
      - banned_words: [speculative, off-book]
  - name: ops
    role: ops
```

The registry of nameable factories lives in `ormica.cortex.loader.RULE_FACTORIES`. To expose your own factory from YAML, register it there before loading the config.

## The standard rule library

Most projects need the same primitives. `ormica.cortex.rules` ships them as one-liner factories so you don't re-implement them:

```python
from ormica.cortex import Constitution
from ormica.cortex.rules import (
    max_depth, block_role, no_child_name, unique_role_in_subtree,    # spawn
    max_tokens, block_prompt_pattern, min_task_description,           # pre
    banned_words, max_response_tokens, min_response_length, require_json,  # post
)

constitution = Constitution([
    max_depth(4),                                # cap tree depth
    block_role("finance"),                       # finance can't spawn
    max_tokens(100_000),                         # org-wide budget cap
    block_prompt_pattern("internal-only"),       # block sensitive keywords
    banned_words({"secret", "confidential"}),    # response content guard
    require_json(),                              # tool-output schema enforcement
])
```

Each factory returns a fully-formed `Rule` with a descriptive `name` and `description`, so violations are self-explanatory in `RuleViolation`. Roll your own `Rule` for the cases these don't cover — they're conveniences, not a closed set.

## Related

- [Pillar 3 — Governance](../architecture/04-governance.md) — the architecture.
- [Pillar 1 — Hierarchy](../architecture/01-hierarchy.md) — how `SpawnPolicy` composes.
- [Reading the Thought Trail](./reading-the-thought-trail.md) — debugging which rule failed.
