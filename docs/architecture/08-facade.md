# Ormica facade — the one-import entry point

**File:** [`ormica/core.py`](../../ormica/core.py)
**Role:** wire arbor + canopy + mycelium + stigma + cortex + observe into a single object — `from ormica import Ormica`.

## The shape

```python
from ormica import Ormica
from ormica.cortex import Constitution
from ormica.observe import TraceObserver

org = Ormica(
    "My SaaS",                           # root node name
    owner="Founder",                     # human-in-the-loop
    policy=None,                         # optional SpawnPolicy (Canopy / ConstitutionPolicy)
    max_depth=8,                         # arbor depth limit
    memory=None,                         # custom Mycelium (else built from below)
    memory_path="./mem.json",            # → FileBackend
    memory_db="./mem.db",                # → SqliteBackend (wins over memory_path)
    signals_half_life=60.0,              # stigma decay knob
    constitution=Constitution([...]),    # cortex / governance
)
```

When the facade is built:
- A `Tree` is created. If `constitution` is set, it's also wrapped as a `ConstitutionPolicy` and composed with whatever `policy` you passed.
- A `Mycelium` is created (custom > sqlite > file > in-memory).
- A `Stigma` is built on top of the Mycelium.
- An `EventBus` is created.

Every facade attribute is publicly accessible: `org.tree` · `org.memory` · `org.signals` · `org.events` · `org.constitution`.

## What it exposes

### Tree ergonomics

```python
ops    = org.spawn("ops", role="operations")
scout  = org.spawn("scout", under=ops, task="map area")
node   = org.find("scout")
org.prune(node)
```

### Colony

```python
org.add(SalesAgent)                # plant one AgentTemplate
org.plant("business")              # plant a whole colony
```

### Tasks

```python
org.task("Reach out to 3 leads", dept="sales", priority="high")
org.task("Forecast Q3 cash flow", dept="finance")

result = org.run(brain=ClaudeBrain())                    # sync
result = await org.arun(brain=AsyncClaudeBrain(), concurrency=5)  # async
```

### Memory

```python
org.write("policy", "no overtime")
org.read("policy").value
org.remember("policy", default="…")
org.scope(node).write("note", "found something")          # author-tagged view
```

### Signals

```python
org.emit("hot_lead", strength=1.0, by=scout)
org.reinforce("hot_lead", amount=0.5, by=ops)
org.sense("hot_lead").strength
org.top_signals(3)
```

### Observability

```python
org.subscribe(LogObserver())
trace = org.trace_for(task_id)        # reads from mycelium first, then TraceObserver
```

### Iteration

```python
for node in org:                       # depth-first walk
    print("  " * node.depth + node.name)

len(org)                                # node count
node in org                             # membership
```

## Composition example — everything at once

```python
from ormica import Ormica
from ormica.brain import ClaudeBrain
from ormica.canopy import Canopy, RoleRisk, RiskLevel
from ormica.cortex import Constitution, Rule
from ormica.observe import TraceObserver

# Governance
constitution = Constitution([
    Rule(name="depth_cap", description="max depth 4",
         check=lambda ctx: ctx["depth"] <= 4, stage="spawn"),
])
# Permission
canopy = Canopy(assessor=RoleRisk({"finance": RiskLevel.ROOT}))

# Facade
org = Ormica(
    "Acme", owner="Founder",
    policy=canopy,                  # canopy governs spawn
    constitution=constitution,      # cortex composes on top
    memory_db="./acme.db",          # persistent state
)
org.plant("business")

# Observability
trail = TraceObserver(store=org.memory)
org.subscribe(trail)

# Work
org.task("Plan Q3 sprint", dept="operations", priority="high")
org.run(brain=ClaudeBrain())

# Inspect
for t in org.tasks:
    trace = org.trace_for(t.id)
    print(f"{t.status}: {trace.entries[0].response_content[:60]}…")
```

## Related

- [Getting started](../getting-started.md) — the minimal Ormica setup.
- [Architecture overview](./README.md) — the four pillars beneath the facade.
- [CLI reference](../reference/cli.md) — building the same facade from `ormica.yaml`.
