# Writing a colony

Add a new industry to Ormica — Python or YAML.

## Option A — Python

Best when your industry has custom logic, dynamic templates, or you want IDE support.

```python
# my_industry.py
from ormica.colony import AgentTemplate, Colony, register


class PMAgent(AgentTemplate):
    name = "pm"
    role = "product"
    task = "Define and prioritize the next sprint"
    system_prompt = (
        "You are the product manager. Pick the smallest valuable next bet. "
        "Coordinate with engineering and design."
    )


class EngAgent(AgentTemplate):
    name = "eng"
    role = "engineering"
    task = "Build the prioritized features"
    system_prompt = (
        "You are the engineering lead. Implement features, fix bugs, "
        "and keep the build green."
    )


class DesignAgent(AgentTemplate):
    name = "design"
    role = "design"
    task = "Make it usable and beautiful"
    system_prompt = "You are the design lead. Wireframe, mock, polish."


@register
class SaasColony(Colony):
    name = "saas"
    description = "Small B2B SaaS team — PM, engineering, design."

    def templates(self):
        return [PMAgent, EngAgent, DesignAgent]
```

Use it:

```python
import my_industry  # noqa — triggers @register

from ormica import Ormica
org = Ormica("My SaaS")
org.plant("saas")
```

The three templates appear as children of the root. Each carries its `system_prompt` in `node.meta`, so when the runtime builds an `Agent` around them, the right voice surfaces automatically.

## Option B — YAML

Best when you don't want users to write Python, or you want declarative configs you can check into the repo.

```yaml
# saas.yaml
name: saas
description: Small B2B SaaS team
templates:
  - name: pm
    role: product
    task: Define and prioritize the next sprint
    system_prompt: |
      You are the product manager. Pick the smallest valuable next bet.

  - name: eng
    role: engineering
    task: Build the prioritized features
    system_prompt: |
      You are the engineering lead. Implement features, fix bugs.

  - name: design
    role: design
    task: Make it usable and beautiful
    system_prompt: You are the design lead.
```

Two ways to use it:

### Via Python

```python
from ormica.colony import load_colony

load_colony("./saas.yaml", register=True)
org.plant("saas")
```

### Via `ormica.yaml`

```yaml
# ormica.yaml
name: My SaaS
industry: ./saas.yaml         # path detected; loaded + registered before plant
brain:
  type: mock
  replies: ["ok"]
```

The CLI's `_build_org` recognizes `.yaml` / `.yml` / path-like values in the `industry` field and loads them before planting.

## Hierarchies (CEO → managers → workers)

The default `Colony.plant` is flat — every template becomes a direct child of root. For hierarchies, override `plant`:

```python
@register
class StartupColony(Colony):
    name = "startup"

    def plant(self, org, *, under=None):
        parent = under or org.root
        ceo = CEOAgent.plant(org, under=parent)
        # Plant managers under the CEO, not root.
        ProductHead.plant(org, under=ceo)
        EngHead.plant(org, under=ceo)
        return [ceo]
```

## Best practices

- **Keep `system_prompt` short.** ~3–5 sentences. The brain already sees role + task; the prompt is for *flavor*, not full instructions.
- **One template = one node = one role.** If you want sub-teams, override `plant`.
- **Don't import `brain` or `cortex` from a template.** Templates are declarative; runtime concerns belong in the runtime.
- **Test by planting and inspecting `node.meta`.** No LLM needed.

```python
def test_pm_plants_with_right_prompt():
    org = Ormica("X")
    node = org.add(PMAgent)
    assert node.role == "product"
    assert "product manager" in node.meta["system_prompt"]
```

## Related

- [Colony architecture](../architecture/06-colony.md) — what's happening under the hood.
- [Pillar 1 — Hierarchy](../architecture/01-hierarchy.md) — node + tree primitives.
