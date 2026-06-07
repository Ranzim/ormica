# Human approvals — keeping a person in the loop

Some agent spawns should never happen without a human saying yes:

- Spawning a `finance` role that will eventually issue refunds.
- Adding a sub-agent during after-hours when no one is reviewing output.
- Onboarding a new `legal` or `compliance` agent.

Canopy (Ormica's permission-chain layer) was designed for exactly this. The decision is split into two pieces:

1. **Risk assessment** — `RiskAssessor` decides *how far up the chain* a spawn request must travel: `AUTO` (parent only), `CHAIN` (N ancestors), `ROOT` (only the human owner).
2. **Approval** — `Approver` is asked at each authority. Always says yes? `AutoApprover`. Always no? `DenyApprover`. Defer to a human? The two approvers in this guide.

## ConsoleApprover — for local development

`ConsoleApprover` prompts the operator over stdin. Approval = anything starting with `y`/`Y`; everything else (including an empty line) denies.

```python
from ormica import Ormica
from ormica.canopy import Canopy, ConsoleApprover, RiskLevel, RoleRisk

canopy = Canopy(
    assessor=RoleRisk({"finance": RiskLevel.ROOT}),
    root_approver=ConsoleApprover(),
)
org = Ormica("Acme", policy=canopy)

org.spawn("scout", role="scout")          # AUTO — no prompt
org.spawn("finance", role="finance")
# prompt → approve spawn 'finance' (role='', risk=root) under 'Acme'? [y/N]:
```

It's the right shape for prototyping. **Don't use it in production** — `input()` blocks the spawning thread until someone answers. Fine on a dev laptop, fatal in an async runner.

## CallbackApprover — the production seam

`CallbackApprover` wraps any Python callable so you can wire the approval to whatever your team actually uses: a Slack interactive message, a queue worker, a small web UI, an on-call paging system. The callable receives the `SpawnRequest` and the `Node` whose authority is being invoked, and returns `bool`.

```python
from ormica.canopy import Canopy, CallbackApprover, RiskLevel, RoleRisk


def slack_approver(request, at):
    ts = post_slack(
        channel="#ops-approvals",
        text=f"Approve spawn of {request.child_name!r} under {at.name!r}?",
    )
    return wait_for_button_press(ts)        # blocks until a human clicks


canopy = Canopy(
    assessor=RoleRisk({"finance": RiskLevel.ROOT}),
    root_approver=CallbackApprover(slack_approver),
)
```

The callback can do anything — read from a queue, POST to your tooling, consult a database, send an email and wait for a webhook. Returning `True` approves; returning `False` raises `SpawnDenied` at the spawn site.

## Composing with cortex Constitution rules

Canopy and `ConstitutionPolicy` compose: both can deny a spawn, neither is silently bypassed.

```python
from ormica.cortex import Constitution, ConstitutionPolicy
from ormica.cortex.rules import max_depth

policy = ConstitutionPolicy(
    Constitution([max_depth(3)]),
    inner=Canopy(
        assessor=RoleRisk({"finance": RiskLevel.ROOT}),
        root_approver=CallbackApprover(slack_approver),
    ),
)
org = Ormica("Acme", policy=policy)
```

Now a spawn must pass *both* the constitution's spawn rules *and* canopy's human approval. The `max_depth(3)` rule fails first if applicable (cheap, no human round-trip); canopy is only consulted if the constitution permits.

## What to use when

| Need | Use |
|---|---|
| Local dev, you're at the terminal | `ConsoleApprover` |
| Production: Slack / email / queue / web UI | `CallbackApprover(your_function)` |
| Always allow (default, dev seed) | `AutoApprover` |
| Always deny (lockdown / tests) | `DenyApprover` |

## Common mistakes

- **Confusing `child_name` and `role`.** `RoleRisk({"finance": RiskLevel.ROOT})` matches when the *child's name* is `"finance"`. If your code does `org.spawn("treasury", role="finance")`, the role-risk map sees `"treasury"`, not `"finance"`. Either match the name to the risk map or write a custom `RiskAssessor`.
- **Forgetting that approvers block.** Especially `ConsoleApprover` — if you call it from an async runner, your event loop stalls until a human types something.
- **Letting `AutoApprover` slip into production.** It's the default if you don't pass `chain_approver=` or `root_approver=`. Audit before shipping.

## See also

- [Pillar 1 — Hierarchy](../architecture/01-hierarchy.md) — the SpawnPolicy seam canopy plugs into.
- [Writing a Constitution](./writing-a-constitution.md) — the other policy layer that composes with canopy.
