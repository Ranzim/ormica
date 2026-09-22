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

**Ormica is the coordination layer for multi-agent AI.** Most systems fall apart on genuinely hard work. A single prompt forgets. A fixed chain of agents shatters the moment reality stops matching the diagram. Ormica takes a different path, drawn from biology and cybernetics. You hand it a goal, and a colony of agents grows to meet it. They spawn the helpers they need, coordinate through a shared signal field instead of chatting back and forth, stay inside the rules you set, check their own work, and leave a complete record of everything they did. When a branch finishes, it is pruned. Nothing is hand wired.

Think of a traditional AI system as a machine. You program it, it runs a fixed script, and it breaks at the first edge case. Ormica is closer to a cybernetic organism. It grows toward the goal, reinforces what works, prunes what does not, heals around failure, and governs itself inside the constraints you define. The colony is the program.

It runs on any model you like, from Claude and Gemini to something local, and scales from your laptop to a room full of machines.

**Architecture at a glance.** Five subsystems, one biological metaphor:

| Subsystem | Role | In one line |
|---|---|---|
| `arbor` | the tree | agents spawn and prune as a living hierarchy |
| `stigma` + `mycelium` | the field | pheromone signals over shared, persistent memory |
| `canopy` | the gate | a permission chain that bounds every spawn |
| `cortex` | the law | a Constitution the model cannot override |
| `observe` | the record | a Thought Trail of every reasoning step |

## Why it exists

Real problems are messy. "Design this system." "Run this back office." "Research this market and tell me where to bet." You cannot flatten work like that into one call or one rigid pipeline. It needs many minds working at once, someone keeping their growth in check, a way to catch mistakes before they ship, and an honest trail you can read afterward.

That is **coordination**, and coordination is the hard part almost every agent tool leaves to you. Ormica is built to be that missing layer, so you can point real, complex work at real models and actually trust what comes back.

## The idea, in one breath

Ants build cathedrals with no architect. No single ant holds the plan. Each one reacts to pheromone trails left in the shared environment, and the structure emerges anyway. Ormica brings that to software through four ideas that fit together.

**A living tree.** You define the goal. The framework grows the agents. They appear when they are needed and vanish when the work is done, so the shape of the system always matches the shape of the task. No fixed chains.

**Coordination through the environment.** Agents leave signals in shared memory, and those signals fade over time. Others follow the strong trails and ignore the weak ones. There is no fragile web of who talks to whom.

**Growth with a leash.** Every new agent has to pass a gate before it is born. Small decisions happen locally. Risky ones climb all the way up to you, the human. The colony can never quietly run away.

**Law the model cannot break.** A Constitution of rules decides what agents are allowed to do, no matter what the model generates. The brain proposes. The cortex decides.

Underneath all of it, every step is written into a Thought Trail you can query later. The black box becomes something you can read.

## Try it in thirty seconds

```bash
pip install ormica
ormica doctor
ormica ask "What is 6 times 7?" --brain gemini
```

One governed call in Python:

```python
from ormica import Ormica
from ormica.brain import GeminiBrain

org = Ormica("Acme")
print(org.ask("Write a one line launch tweet for a developer tool", brain=GeminiBrain()))
```

Or grow a colony that plans and runs itself, with memory that survives a restart:

```python
org = Ormica("My SaaS", memory_db="acme.db")
org.plant("business")                              # departments appear under the root
org.task("Reach out to three leads", dept="sales", priority="high")
org.run(brain=GeminiBrain())
```

## When it fits, and when it does not

Reach for Ormica when the work is genuinely complex and you want many agents cooperating on it, with governance, cost limits, retries, memory, and a record you can audit. If all you need is a single answer, just call the model. You do not need a colony for that.

Here is the honest line on how it differs from a chatbot. A chat assistant does a task for you while you watch. Ormica is the library you build on so that your own software can do that kind of work on its own, at whatever scale you need.

## What it can actually do

- **Break big goals down and run them in parallel.** A planner turns a goal into a dependency graph, and an agent that is in over its head can spawn sub agents that spawn their own.
- **Give answers that are actually right.** Check a response against a real test, run the code and read the output, validate a schema, ask a judge, and retry until it passes. Results can be typed and structured, not loose prose.
- **Steer toward what you care about.** Tell it to favor cost, quality, or speed, and the colony changes how deeply it thinks, how hard it verifies, and how much it parallelizes.
- **Keep going when things fail.** Retries with backoff, a circuit breaker that pulls a broken branch out of rotation, a dead letter queue, and self repair that prunes a failing branch and grows a fresh one.
- **Remember, resume, and scale out.** Pluggable memory that survives restarts, runs you can resume after a crash, and many worker processes draining one shared queue across machines with no central dispatcher.
- **Stay fast and cheap.** A caching brain skips repeated calls, and every run reports the tokens and time it spent.
- **Stay safe.** Sandboxed code execution, human approval gates for risky actions, and secrets kept out of the logs.
- **Let you watch it think.** The full Thought Trail plus a dependency free live 3D view of the colony as it works.
- **Use any model.** Claude, Gemini, and OpenAI natively, plus one universal adapter for Ollama, OpenRouter, Groq, Together, DeepSeek, vLLM, and more.

## Examples worth running

Each one is a real, runnable program, offline by default so you can try it without a key.

- [**compute_lab**](./examples/compute_lab) shows answers that are verified by actually running them in the sandbox, watchable live in the dashboard.
- [**architect**](./examples/architect) is a colony of specialists that designs a real software architecture and hands back a validated, structured result.
- [**distributed_colony**](./examples/distributed_colony) runs many worker processes over one shared queue with no dispatcher.
- [**forest_vote**](./examples/forest_vote) runs the same goal through many independent colonies and takes the vote, because agreement beats a single lucky try.
- [**live_swarm**](./examples/live_swarm) is a self growing colony that lights up every part of the live graph at once.

## Install

```bash
pip install ormica                # the core, with a mock brain and no LLM cost
pip install ormica[gemini]        # add Google Gemini
pip install ormica[claude]        # add Anthropic Claude
pip install ormica[universal]     # add OpenAI, Ollama, Groq, and every OpenAI compatible provider
pip install ormica[all]           # everything
```

Needs Python 3.10 or newer. One install, every major model. The full recipe list lives in [the provider guide](./docs/guides/llm-providers.md).

Hacking on Ormica itself? Clone the repo, run `pip install -e ".[dev]"`, then `pytest`. The whole suite is over 930 tests and finishes in a couple of seconds with no API keys.

## Docs

- [Getting started](./docs/getting-started.md), from install to your first colony
- [Concepts](./docs/concepts.md), the stigmergy idea in depth
- [Guides](./docs/README.md), for colonies, tools, rules, verification, distributed runs, the Forest, and the dashboard
- [Architecture](./docs/architecture/README.md), one page per part of the engine
- [CLI reference](./docs/reference/cli.md), for `ask`, `solve`, `run`, `resume`, `worker`, `plan`, `doctor`, and more

## Roadmap

The four pillars, the runtime, persistence, verification, typed results, recursive delegation, distributed workers, multi colony voting, self healing, a live 3D dashboard, and a full CLI are all shipped and on PyPI today. Next up are streaming responses, more first party integrations, and hardening for very large scale. A hosted platform is the long term goal.

## Contributing

The colony is young, and new contributors shape its character. Start with [Your First PR](./docs/guides/your-first-pr.md), then read [CONTRIBUTING.md](./CONTRIBUTING.md) to see where things go. Run `pytest` and `ruff check .` before you push. Please be kind, per the [Code of Conduct](./CODE_OF_CONDUCT.md). Found a security issue? See [SECURITY.md](./SECURITY.md).

## License

MIT. Yours to use, change, and build on.

<div align="center">
<br>

**Ormica.** Organize like a colony. Grow like a forest. Decide like an organization. Audit like infrastructure.

`#AgenticAI` &nbsp; `#MultiAgentSystems` &nbsp; `#Stigmergy` &nbsp; `#SwarmIntelligence` &nbsp; `#Emergence` &nbsp; `#LLM` &nbsp; `#AIAgents` &nbsp; `#DistributedSystems` &nbsp; `#Autonomy` &nbsp; `#Python`

</div>
