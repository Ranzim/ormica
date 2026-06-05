# Colony — industry templates

**Module:** `colony`
**Role:** the place where industries plug in on top of the universal core.

## What it is

The core engine (`arbor` · `canopy` · `mycelium` · `stigma`) knows nothing about business, healthcare, or supply chains. **Colony** is where domain-specific knowledge lives — as **AgentTemplates** grouped into **Colonies**.

```python
from ormica import Ormica

org = Ormica("Acme")
org.plant("business")              # spawns operations / sales / marketing / finance
```

Plant a colony, and the right departments appear under root with the right roles, tasks, and system prompts — all derived from declarative templates.

## AgentTemplate — one declared agent

```python
from ormica.colony import AgentTemplate

class SalesAgent(AgentTemplate):
    name = "sales"
    role = "sales"
    task = "Find qualified leads and close deals."
    system_prompt = "You are the sales lead. Identify qualified leads..."
```

A template is **purely declarative** — it doesn't hold a Brain or run anything. Calling `SalesAgent.plant(org)`:

1. Spawns a node with the template's name / role / task.
2. Writes the template's `system_prompt` into `node.meta["system_prompt"]`.

When the runtime later builds an `Agent` around that node, the system prompt is automatically picked up. Same with role and task — they end up in the system message the Brain sees.

## Colony — a group of templates

```python
from ormica.colony import Colony, register

@register
class BusinessColony(Colony):
    name = "business"
    description = "Generic business — operations, sales, marketing, finance."

    def templates(self):
        return [OperationsAgent, SalesAgent, MarketingAgent, FinanceAgent]
```

The `@register` decorator adds the colony to the registry under `name`, making it pluggable via `org.plant("business")`. Both built-in colonies live in:

- [`ormica/colony/business/`](../../ormica/colony/business/) — operations · sales · marketing · finance
- [`ormica/colony/supply_chain/`](../../ormica/colony/supply_chain/) — procurement · warehouse · logistics · quality

## YAML colonies — no Python required

For non-Python contributors (or anyone wanting declarative industries), define a colony in YAML:

```yaml
# my-saas.yaml
name: my_saas
description: B2B SaaS organization
templates:
  - name: product
    role: product
    task: Define and prioritize features
    system_prompt: |
      You lead product. Pick the smallest valuable next bet.
  - name: engineering
    role: engineering
    task: Build the prioritized features
  - name: sales
    role: sales
    task: Find and close customers
```

Then either:

```python
from ormica.colony import load_colony
load_colony("my-saas.yaml", register=True)
org.plant("my_saas")
```

Or set it on `ormica.yaml`:

```yaml
industry: ./my-saas.yaml         # auto-detected as a path
```

The CLI's `_build_org` recognizes `.yaml`/`.yml` paths and loads + registers automatically before planting.

| Type | Where | Role |
|---|---|---|
| `AgentTemplate` | [`ormica/colony/base.py`](../../ormica/colony/base.py) | Declarative agent description |
| `Colony` | [`ormica/colony/base.py`](../../ormica/colony/base.py) | Base for industry colonies |
| `@register` / `get_colony` / `colonies` | [`ormica/colony/registry.py`](../../ormica/colony/registry.py) | Name-based registry |
| `load_colony` | [`ormica/colony/yaml_loader.py`](../../ormica/colony/yaml_loader.py) | YAML → dynamic Colony subclass |

## How a planted node becomes a thinking Agent

```
SalesAgent (template)
    └─ org.add(SalesAgent) or org.plant("business")
         └─ Tree.spawn(...) creates a Node
              ├─ node.role = "sales"
              ├─ node.task = "Find qualified leads..."
              └─ node.meta["system_prompt"] = "You are the sales lead..."
                  
At runtime, the Agent built around this node sees:
   system = "You are the sales lead...\n\nYour role: sales.\n\nYour task: Find qualified leads..."
```

The system prompt the Brain sees is composed from: explicit `Agent(system_prompt=...)` ▸ template prompt ▸ role ▸ task.

## Design invariants

- **Templates are declarative.** No imports of Brain or Cortex. A template never runs anything; it only describes what a node looks like.
- **Hierarchies are user-overridable.** The default `Colony.plant` spawns one node per template under root (flat). For nested structures (CEO → managers → workers), override `plant()`.
- **Names are registry keys.** `name` is required on a Colony to be registered. Templates can omit it (falls back to lowercase class name).

## Related

- [Writing a colony](../guides/writing-a-colony.md) — Python and YAML walkthrough.
- [Pillar 1 — Hierarchy](./01-hierarchy.md) — what planting actually does to the tree.
- [Runtime](./07-runtime.md) — how planted nodes turn into running Agents.
