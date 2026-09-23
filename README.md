<div align="center">

# 🐜 Ormica

### An Autonomous Coordination Engine for multi-agent AI

> Seed the colony. Let the organization emerge.

[![PyPI](https://img.shields.io/pypi/v/ormica.svg)](https://pypi.org/project/ormica/)
[![CI](https://github.com/Ranzim/ormica/actions/workflows/ci.yml/badge.svg)](https://github.com/Ranzim/ormica/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Ranzim/ormica/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/Ranzim/ormica/security/code-scanning)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

`#AgenticAI` &nbsp; `#MultiAgent` &nbsp; `#Stigmergy` &nbsp; `#SwarmIntelligence` &nbsp; `#LLM` &nbsp; `#DistributedSystems` &nbsp; `#Python`

</div>

A biologically inspired runtime where LLM agents **self organize, self verify, self heal, and self optimize.** You give a goal. A colony grows to meet it, coordinates through a shared pheromone field instead of chatting, stays inside rules the model cannot override, checks its own work, and prunes itself when done. The more you run it, the sharper it gets at your work.

Traditional agent stacks are machines. You wire a fixed graph and it breaks at the first edge case. Ormica is a cybernetic organism. It grows toward the goal, reinforces what works, heals around failure, and governs itself inside your constraints. **The colony is the program.**

## Architecture

| Subsystem | Role | In one line |
|---|---|---|
| `arbor` | the tree | agents spawn and prune as a living hierarchy |
| `stigma` + `mycelium` | the field | pheromone signals over shared, persistent memory |
| `canopy` | the gate | a permission chain and budget governor that bound every spawn |
| `cortex` | the law | a Constitution the model cannot override |
| `observe` | the record | a Thought Trail of every reasoning step |

## Quickstart

```bash
pip install ormica
ormica solve "Design a URL shortener for a billion links. Pick the data model, the hashing scheme, and the cache strategy, and justify each choice." --brain gemini --preference quality
```

One command plants a colony, decomposes the goal into a dependency graph, runs the pieces in parallel, verifies the result, and returns a structured answer with a full trail.

```python
from ormica import Ormica
from ormica.brain import GeminiBrain

org = Ormica("Acme", memory_db="acme.db")     # memory survives restarts
org.plant("business")                          # departments appear under the root
org.dispatch("Follow up with warm leads", kind="outreach",
             candidates=["closer", "nurture"], brain=GeminiBrain())
```

Reach for it when the work is genuinely complex and needs many agents with governance, cost limits, memory, and an audit trail. For a single answer, just call the model.

## What makes it different

- **Emergent, not wired.** A planner turns a goal into a dependency graph, and an overloaded agent spawns sub agents that spawn their own. No fixed chains.
- **Coordination through the environment.** Agents leave decaying pheromone signals in shared memory. Strong trails win, weak ones fade. No message spaghetti.
- **Governed by construction.** Every spawn passes a permission gate, a budget governor caps spend, and risky actions escalate to a human.
- **Law the model cannot break.** A Constitution decides what agents may do, whatever the model generates. The brain proposes, the cortex decides.
- **Verified answers.** Run the code, check the schema, ask a judge, retry until it passes. Typed, structured results, not loose prose.
- **Self healing.** Retries with backoff, a circuit breaker, a dead letter queue, and respawn of failed branches.
- **Self optimizing.** `dispatch` reinforces whatever verified and came back cheap, learning the best agent, tool, and decomposition for each kind. Ant colony optimization for agent workflows.
- **Scales out.** Many workers drain one shared queue across machines with no central dispatcher, and any run resumes after a crash.
- **Any model.** Claude, Gemini, and OpenAI natively, plus one universal adapter for Ollama, OpenRouter, Groq, Together, DeepSeek, and vLLM.
- **Auditable and observable.** The full Thought Trail plus a dependency free live 3D view of the colony as it works.

## Make it yours

The core is domain blind. It coordinates, governs, verifies, and learns, but it never hard codes what a sale, a netlist, or a protein is. You bring the agents, the tools, and the kinds of work. Any Python function or MCP server becomes a tool. **The `kind` is the seam,** and the colony learns a separate specialist for each one, in your vocabulary.

| You are a | You wire in | The colony learns |
|---|---|---|
| Founder or operator | inbox, CRM, analytics | which outreach closes your funnel |
| Researcher or analyst | solver, sandbox, ground truth | which method holds up for your problems |
| Engineer or hardware team | build tool, formal checker | the flows that pass, fully audited |
| Creative or media team | renderer, editor | the stages worth running in parallel |

## How it compares

The closest neighbors are the multi-agent orchestration frameworks. Where they hand you wiring and prompts, Ormica hands you a colony that organizes, governs, and improves itself.

| Framework | Coordination model | What Ormica does instead |
|---|---|---|
| LangGraph | a state graph you wire by hand | grows the graph from the goal, no fixed wiring |
| CrewAI | fixed crews with assigned roles | roles spawn on demand and prune when done |
| AutoGen | agents that coordinate by chatting | a shared pheromone field, not conversation |
| OpenAI Agents SDK | handoffs across a fixed set | emergent hierarchy under a permission chain and budget cap |
| MetaGPT | a hard coded software company SOP | domain blind core, you bring the roles and the work |

The real difference is three things none of them combine. **Stigmergy and emergence** for coordination, a **cortex the model cannot override** for governance, and a **learning flywheel** that tunes the engine to your domain over time.

## Examples

Runnable and offline by default, no key needed:
[compute_lab](./examples/compute_lab) verified sandbox execution &nbsp;·&nbsp; [architect](./examples/architect) specialist design colony &nbsp;·&nbsp; [distributed_colony](./examples/distributed_colony) dispatcherless workers &nbsp;·&nbsp; [forest_vote](./examples/forest_vote) multi colony voting &nbsp;·&nbsp; [live_swarm](./examples/live_swarm) the live 3D graph.

## Install

```bash
pip install ormica            # core and mock brain, no LLM cost
pip install ormica[gemini]    # add Google Gemini
pip install ormica[claude]    # add Anthropic Claude
pip install ormica[universal] # add OpenAI, Ollama, Groq, every OpenAI compatible provider
pip install ormica[all]       # everything
```

Python 3.10 or newer. Over 960 tests, no API keys, run in seconds with `pip install -e ".[dev]" && pytest`.

## Docs

[Getting started](./docs/getting-started.md) &nbsp;·&nbsp; [Concepts](./docs/concepts.md) &nbsp;·&nbsp; [Guides](./docs/README.md) &nbsp;·&nbsp; [Architecture](./docs/architecture/README.md) &nbsp;·&nbsp; [CLI reference](./docs/reference/cli.md) &nbsp;·&nbsp; [Your First PR](./docs/guides/your-first-pr.md) &nbsp;·&nbsp; [Security](./SECURITY.md)

## License

MIT. Yours to use, change, and build on.

<div align="center">
<br>

**Ormica.** Organize like a colony. Grow like a forest. Decide like an organization. Audit like infrastructure.

`#AgenticAI` &nbsp; `#MultiAgentSystems` &nbsp; `#Stigmergy` &nbsp; `#SwarmIntelligence` &nbsp; `#Emergence` &nbsp; `#LLM` &nbsp; `#AIAgents` &nbsp; `#DistributedSystems` &nbsp; `#Autonomy` &nbsp; `#Python`

</div>
