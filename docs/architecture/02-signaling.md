# Pillar 2 — Stigmergic Signaling

**Modules:** `mycelium` · `stigma`
**Solves:** noisy, error-prone agent-to-agent chat. Coordination through a shared **signal field**, not direct messages.

## What it is

In a real ant colony, ants don't message each other. They drop **pheromones** in the environment; other ants detect them, follow the strong trails, and ignore the weak ones. Strong trails are reinforced when more ants use them. Weak ones evaporate. This is called **stigmergy** — coordination through environmental signals.

Ormica does the same thing:

- **`mycelium`** is the substrate — the underground network that links every node. It's a shared key-value store with author tags, timestamps, optional TTL, and a pluggable backend.
- **`stigma`** is the pheromone layer on top. Agents `emit` and `reinforce` signals on topics; intensity decays exponentially; `evaporate` prunes weak trails.

## Mycelium — shared memory

```python
from ormica.mycelium import Mycelium

mem = Mycelium()
mem.write("policy", "no overtime", author="founder", ttl=3600)
mem.read("policy").value           # → "no overtime"
mem.by_author("founder")           # → all entries written by 'founder'
```

| Type | Where | Role |
|---|---|---|
| `Mycelium` | [`ormica/mycelium/mycelium.py`](../../ormica/mycelium/mycelium.py) | The KV interface; supports scoping per-node |
| `Entry` | [`ormica/mycelium/entry.py`](../../ormica/mycelium/entry.py) | key · value · author · written_at · expires_at · meta |
| `Backend` (protocol) | [`ormica/mycelium/backend.py`](../../ormica/mycelium/backend.py) | The persistence seam |
| `InMemoryBackend` | [`ormica/mycelium/backend.py`](../../ormica/mycelium/backend.py) | Default; loses state at exit |
| `FileBackend` | [`ormica/mycelium/file_backend.py`](../../ormica/mycelium/file_backend.py) | JSON file; crash-safe via atomic rename |
| `SqliteBackend` | [`ormica/mycelium/sqlite_backend.py`](../../ormica/mycelium/sqlite_backend.py) | O(1) writes; WAL journal mode |

See [Persistence guide](../guides/persistence.md) for choosing a backend.

## Stigma — pheromone trails

```python
from ormica.stigma import Stigma

sig = Stigma(mem, half_life=60.0, floor=0.01)

sig.emit("path_to_food", strength=1.0, by="ant-1")
sig.reinforce("path_to_food", amount=1.0, by="ant-2")
sig.reinforce("path_to_food", amount=1.0, by="ant-3")

sig.sense("path_to_food").strength   # → 3.0 (with exponential decay applied)
sig.top(3)                            # → strongest 3 trails
sig.evaporate()                       # → drops trails below `floor`
```

| Type | Where | Role |
|---|---|---|
| `Stigma` | [`ormica/stigma/stigma.py`](../../ormica/stigma/stigma.py) | emit / reinforce / sense / trails / top / evaporate |
| `Signal` | [`ormica/stigma/signal.py`](../../ormica/stigma/signal.py) | topic · strength · sources · last_touched + `strength_at(now, half_life)` |

### Decay math

Strength decays exponentially:

```
strength(t) = stored_strength × 0.5 ** ((now - last_touched) / half_life)
```

Decay is **lazy** — Ormica never runs a background "decay tick". `sense()` and `evaporate()` compute the current strength at read time. Reinforcement adds to the current decayed value, not the stored value.

## How they compose

Stigma writes signals into mycelium under the `stigma/` key prefix:

```
mycelium ─┬─ "policy"               (regular entry)
          ├─ "rule"                  (regular entry)
          ├─ "stigma/path_to_food"   (stigma signal)
          └─ "tasks/abc123"          (runtime task record)
```

That means swapping `Mycelium`'s backend (e.g., to `SqliteBackend`) automatically gives stigma persistence too. Tested in [`tests/test_sqlite_backend.py`](../../tests/test_sqlite_backend.py).

## Why this beats agent-to-agent chat

| Problem with chat | How signaling solves it |
|---|---|
| Messages get lost / duplicated | Signals are state, not events |
| N×N message complexity | O(N) writes into a shared field |
| No natural way to "fade" stale info | Built-in exponential decay |
| Easy to crash one agent by spamming another | Agents read at their own pace |
| Hard to know "who confirmed this?" | `sources: set[str]` on every signal |

## Related

- [Pillar 1 — Hierarchy](./01-hierarchy.md) — every signal can be scoped to a node.
- [Persistence guide](../guides/persistence.md) — `FileBackend` vs `SqliteBackend`.
- [Pillar 4 — Observability](./05-observability.md) — events vs signals (different abstractions).
