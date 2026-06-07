# Pillar 1 — Hierarchical Structure

**Modules:** `arbor` · `canopy`
**Solves:** the *Chaos Trap*. Every agent has a clear scope, a bound context, and a direct reporting line.

## What it is

`arbor` is the tree. Every agent in the colony is a `Node` with a parent and (optionally) children. The root is you — the human owner. Below the root grow departments (Caste), and below those grow workers.

`canopy` is the gate. Before any new node can be spawned, the request rises through a permission chain — sometimes the parent can approve it alone, sometimes it must reach all the way to the root owner. This is what stops the "infinite agent explosion" problem.

```
Root (you)
 │
 ├── operations (Caste)
 │    ├── scout-1 (Worker)
 │    └── scout-2 (Worker)
 │
 ├── sales (Caste)
 │    └── hunter-1 (Worker)
 │
 └── finance (Caste)
```

## The tree primitives — arbor

```python
from ormica.arbor import Tree

tree = Tree("HQ", owner="Founder", max_depth=8)
ops    = tree.spawn(tree.root, "ops",    role="operations")
scout  = tree.spawn(ops,        "scout", role="recon", task="map the area")

scout.depth          # → 2
scout.path()         # → [HQ, ops, scout]
tree.prune(ops)      # removes ops + scout from the tree
```

| Type | Where | Role |
|---|---|---|
| `Node` | [`ormica/arbor/node.py`](../../ormica/arbor/node.py) | One agent — id, name, role, task, parent, children, state, meta |
| `Tree` | [`ormica/arbor/tree.py`](../../ormica/arbor/tree.py) | The colony's skeleton; owns spawn, prune, walk |
| `Branch` | [`ormica/arbor/branch.py`](../../ormica/arbor/branch.py) | A subtree view |
| `SpawnPolicy` | [`ormica/arbor/policy.py`](../../ormica/arbor/policy.py) | The seam where canopy / cortex plug in |

## The permission chain — canopy

Every `Tree.spawn` call asks its `SpawnPolicy` whether the request is allowed. Canopy's policy assesses the request's **risk level** and routes the decision accordingly:

| Risk | Who decides | Use case |
|---|---|---|
| `AUTO` | Parent alone (allowed without asking) | Spawning a low-risk scout |
| `CHAIN` | The N nearest ancestors must agree | Spawning a department lead |
| `ROOT` | Only the root owner can approve | Spawning anything that touches money |

```python
from ormica.arbor import Tree
from ormica.canopy import Canopy, RoleRisk, RiskLevel, DenyApprover

canopy = Canopy(
    assessor=RoleRisk(
        {"finance": RiskLevel.ROOT, "scout": RiskLevel.AUTO},
        default=RiskLevel.CHAIN,
    ),
    chain_levels=2,
    root_approver=DenyApprover(),     # swap for a CLI or HTTP approver
)

tree = Tree("HQ", policy=canopy)
tree.spawn(tree.root, "scout")         # AUTO → allowed
tree.spawn(tree.root, "finance")       # ROOT → DenyApprover says no → SpawnDenied
```

| Type | Where | Role |
|---|---|---|
| `Canopy` | [`ormica/canopy/policy.py`](../../ormica/canopy/policy.py) | The SpawnPolicy impl |
| `RiskLevel` | [`ormica/canopy/risk.py`](../../ormica/canopy/risk.py) | AUTO / CHAIN / ROOT enum |
| `RoleRisk` / `StaticRisk` | [`ormica/canopy/risk.py`](../../ormica/canopy/risk.py) | RiskAssessor implementations |
| `AutoApprover` / `DenyApprover` / `ConsoleApprover` / `CallbackApprover` | [`ormica/canopy/approver.py`](../../ormica/canopy/approver.py) | Approver implementations — auto, deny, terminal-prompt, custom callable. See [Human approvals](../guides/human-approvals.md). |

## How they compose

```python
from ormica import Ormica
from ormica.canopy import Canopy, RoleRisk, RiskLevel

org = Ormica("Acme", owner="Founder", policy=Canopy(
    assessor=RoleRisk({"finance": RiskLevel.ROOT}),
))
org.plant("business")     # 4 departments; root permits each AUTO spawn
```

## Invariants

- **Trees are sync.** Tree operations don't touch network or LLMs — keep them fast.
- **`SpawnPolicy` is one method.** Anything that decides "may this spawn?" implements `allow(parent, child_name) → bool`. Canopy is one; `ConstitutionPolicy` (in `cortex`) is another. They compose.
- **Pruning is permanent.** `tree.prune(node)` removes the node and its entire subtree from the index and marks every member `PRUNED`.

## Related

- [Pillar 3 — Governance](./04-governance.md) — how `ConstitutionPolicy` composes with `Canopy`.
- [Pillar 2 — Signaling](./02-signaling.md) — how nodes coordinate once they exist.
- [Writing a Constitution](../guides/writing-a-constitution.md) — rules that gate spawn.
- [Human approvals](../guides/human-approvals.md) — `ConsoleApprover` and `CallbackApprover` for keeping a person in the loop.
