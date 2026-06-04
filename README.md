<div align="center">

# 🐜 Ormica

### Build agentic software that organizes itself — like an ant colony.

*Not pipelines. Not chains. A living hierarchy of AI agents that spawns, signals, prunes, and grows — with every decision traceable back to root.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status: Early Development](https://img.shields.io/badge/status-early%20development-orange.svg)]()

</div>

---

## What is Ormica?

Ormica is an open-source framework for building **self-organizing AI agent systems** that run real business operations. Instead of one large model doing everything, or a fixed chain of steps, Ormica grows a **living tree of agents** that:

- **Spawn** sub-agents when a task is too complex for one agent
- **Signal** each other through shared memory (like ant pheromones)
- **Ask permission** before growing — every spawn request rises up to the root owner
- **Prune** weak branches that produce nothing
- **Remember** across sessions through a shared memory layer

You stay at the **root**. The system grows beneath you — powerful, but never out of control.

---

## The three ideas behind Ormica

Ormica fuses three concepts into one framework:

| Concept | What it gives Ormica |
|---|---|
| 🐜 **Ant colony intelligence** (stigmergy) | Agents coordinate through signals, not central commands. Intelligence emerges from simple local rules. |
| 🌲 **Random forest structure** | Many branches explore a problem in parallel, each from a different angle, growing to any depth. |
| 🏛️ **Organizational theory** | A permission chain controls growth. Every new agent is approved up the hierarchy — just like hiring in a real company. |

---

## Why Ormica is different

| | LangChain / CrewAI / AutoGen | **Ormica** |
|---|---|---|
| Structure | Fixed chains / graphs | Living tree, grows to N depth |
| Agent creation | Defined upfront | Self-spawning on demand |
| Growth control | None built in | Permission propagates to root |
| Coordination | Direct messaging | Stigmergic signals + emergence |
| Focus | General purpose | Business operations, any industry |

---

## How it handles *any* industry

The core engine knows **nothing** about any specific industry. It only knows how to grow trees, pass signals, control permission, and store memory.

Industries plug in on top as **colonies**. The same engine runs a hospital, a supply chain, or a solo startup — without changing a single line of core code.

```python
org = Ormica("My Company", owner="Founder")

org.plant("supply_chain")   # or "healthcare", "ecommerce", "saas"...

org.run()
```

To support a brand-new industry, you write one `colony.yaml` describing its structure and a few agent classes. The core does the rest.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  INTERFACE   CLI · Dashboard · Approval inbox     │  how humans interact
├─────────────────────────────────────────────────┤
│  COLONY      industry agents plug in here         │  any industry
├─────────────────────────────────────────────────┤
│  CORE ENGINE                                      │  universal, never changes
│    arbor     tree · branching · N-depth           │
│    stigma    signals · emergence                  │
│    canopy    permission · root control            │
│    mycelium  shared memory                        │
├─────────────────────────────────────────────────┤
│  CORTEX      pluggable LLM (Claude/GPT/local)     │  the thinking
├─────────────────────────────────────────────────┤
│  INTEGRATIONS  memory · comms · data · finance    │  acting in the real world
└─────────────────────────────────────────────────┘
```

### The modules — every name *is* its concept

| Module | Biological metaphor | What it does |
|---|---|---|
| `arbor/` | tree | Node, branch, root — the tree structure and N-depth growth |
| `stigma/` | ant pheromones | Signals, trails, evaporation — emergent coordination |
| `canopy/` | forest canopy controlling light | Permission propagation, risk assessment, root control |
| `mycelium/` | underground fungal network | Shared memory all agents read and write |
| `cortex/` | brain | Pluggable LLM engine (Claude, OpenAI, Gemini, local) |
| `colony/` | living community | Pre-built agents per industry |

---

## Quick start

> ⚠️ Ormica is in early development. The API below is the target design — not all of it works yet. See the [roadmap](#roadmap).

```bash
pip install ormica
```

```bash
ormica init my-company --industry saas
ormica run
```

Or in code:

```python
from ormica import Ormica
from ormica.colony.business import OperationsAgent, SalesAgent

org = Ormica("My SaaS", owner="You")

org.add(OperationsAgent)
org.add(SalesAgent)

org.task("Follow up with 3 leads", dept="sales", priority="high")

org.run()
```

---

## The permission chain — why you stay in control

When an agent wants to spawn a sub-agent, it doesn't just do it. The request **rises up the tree**:

```
Sub-agent wants to spawn
        ↑ asks its parent
Parent agent
        ↑ forwards up if risk is high
Department agent
        ↑ propagates to root
YOU (root owner)
        ↓ approve or deny
Decision flows back down
```

Three permission levels keep growth controlled:

- **AUTO** — low risk, parent approves alone
- **CHAIN** — medium risk, propagates up a few levels
- **ROOT** — high risk, only you can approve

This is what prevents the "infinite agent explosion" problem that breaks naive multi-agent systems.

---

## Project structure

```
ormica/
├── ormica/
│   ├── arbor/         tree · branching · N-depth
│   ├── stigma/        ant signals · emergence
│   ├── canopy/        permission chain · root control
│   ├── mycelium/      shared memory · knowledge
│   ├── cortex/        LLM engine · pluggable AI
│   ├── colony/        pre-built agents · industries
│   ├── integrations/  real-world connectors
│   ├── plugins/       community extensions
│   ├── config/        settings + schema
│   ├── observe/       logs · metrics · trace
│   └── cli/           ormica run / init / status
├── examples/          solo_founder · supply_chain · custom
├── tests/             unit · integration · mocks
├── docs/              concepts · quickstart · api
└── pyproject.toml
```

---

## Roadmap

- [x] Concept + architecture design
- [x] Repository structure
- [ ] **Core engine** — `arbor` + `canopy` + `mycelium` (in progress)
- [ ] `cortex` — Claude / OpenAI adapters
- [ ] `stigma` — signal + emergence engine
- [ ] `colony` — business department agents
- [ ] CLI — `ormica init / run / status`
- [ ] Integrations — Gmail, Notion, GitHub, Stripe
- [ ] Observability dashboard
- [ ] Ormica Cloud (hosted platform)

---

## Contributing

Ormica is early and we'd love help. See [CONTRIBUTING.md](CONTRIBUTING.md). Good first areas: new colony agents, LLM adapters, integrations, and docs.

---

## License

MIT — see [LICENSE](LICENSE). Free to use, modify, and build on.

---

<div align="center">

**Ormica** — *organize like a colony, grow like a forest, decide like an organization.*

</div>
