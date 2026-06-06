<div align="center">

# 🐜 Ormica
### An Autonomous Coordination Engine
> **Seed the colony. Let the organization emerge.**

[![PyPI](https://img.shields.io/pypi/v/ormica.svg)](https://pypi.org/project/ormica/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 362 passing](https://img.shields.io/badge/tests-361%20passing-success.svg)]()
[![Status: v0.1](https://img.shields.io/badge/status-v0.1-orange.svg)]()
[![Concept: Computational Stigmergy](https://img.shields.io/badge/concept-computational%20stigmergy-7a4cff.svg)]()

</div>

---

> Traditional AI systems are **machines** — programmed to perform tasks until they fail.
> **Ormica is a cybernetic organism** — designed to evolve within your business architecture.

Ormica is an **open-source coordination framework** for building agentic systems that scale through biological principles. Instead of brittle chains or static pipelines, it provides the *infrastructure* to **spawn**, **signal**, **prune**, and **govern** a living hierarchy of AI agents.

---

## 🗺️ The Living Colony

<div align="center">
  <img src="docs/diagrams/02-living-colony.png" alt="The Living Colony — root, departments, workers, signal trails" width="820">
</div>

Every node is an ant. **Solid arrows** are the spawn hierarchy — every node has a parent, every spawn was approved. **Dashed amber arrows** are stigmergic signals: ① a scout senses a hot lead → hunter, ② hunter closes the deal → finance, ③ finance reports cash → root. *Brightness encodes signal intensity; thickness encodes reinforcement count.* You stay at the root; the colony grows beneath you.

---

## 🧬 The Ormica Philosophy: *"Computational Stigmergy"*

Four biological principles, one architecture.

### 🌲 Emergent Hierarchy — `arbor`
You define the *goals*; the framework grows the *tree*. Agents are spawned dynamically to meet demand, creating a depth-first hierarchy that is as complex or as simple as the task requires. No fixed graphs. No predefined chains.

### 🐜 Stigmergic Coordination — `stigma` + `mycelium`
Agents do not rely on fragile message-passing. They post state, intent, and progress to a **shared digital pheromone field**. Other agents detect strong trails and follow; weak signals evaporate. Coordination is *emergent*, not orchestrated.

### 🏛️ Permission Chain — `canopy`
The engine prevents agent runaway. **Every sub-agent birth** must pass through a permission gate — `AUTO` (parent alone), `CHAIN` (N ancestors), or `ROOT` (only you). High-risk growth propagates all the way to the human owner. The colony remains aligned with your core directives.

### ⚖️ Constitutional Governance — `cortex`
The colony's *law*. Hard constraints and soft policies encoded as `Rule` objects. Where the **brain** generates a response, the **cortex** decides whether it's permissible. Anatomically and architecturally: the brain *acts*; the cortex *inhibits*.

### 🍄 Persistent Memory — `mycelium`
The colony maintains a shared underground network of knowledge. Agents read and write to this state-layer with full author tags, timestamps, and TTL. Pluggable backends (`FileBackend`, `SqliteBackend`) keep state across process restarts. **The system learns from its own history rather than starting from zero.**

### 📡 The Thought Trail — `observe`
Every reasoning step — messages, tool calls, response, tokens — captured and tied to the task that triggered it. Not just *what* happened, but *why the colony chose that path*. Queryable via `org.trace_for(task_id)`. The Black-Box Problem, solved.

---

## 🏗️ Why this is a *Framework*, not just *Software*

| | What you'd normally write | What Ormica gives you |
|---|---|---|
| 🧠 **You provide** | Individual agent actions, prompts, glue code | The *intent* — a colony config + a few tools |
| 🦴 **Ormica provides** | (you wire it together) | **The nervous system** — `arbor`, `stigma`, `mycelium`, `cortex`, `observe` |
| 🏥 **Industry** | Hard-coded for one domain | **Industry-agnostic core** — same engine runs a hospital, a supply chain, a solo founder, just by swapping a colony |
| 💬 **Failure model** | "Catch and retry" | **Bounded blast radius** — a failed task ≠ a dead colony; a prunable branch ≠ tree death |
| 🔭 **Observability** | Logs you grep later | **Thought Trail** — structured per-task reasoning capture, persisted |

You're not writing the colony. You're writing the colony's *constitution*.

---

## 🔬 Engineered for Distributed Systems

Multi-agent AI hits the same problems distributed systems solved 40 years ago. Ormica answers each one explicitly:

| Distributed-systems problem | Ormica's answer |
|---|---|
| Coordination without central commands | **Stigmergy** — agents read/write a shared signal field; strong trails reinforce, weak ones decay |
| Bounded growth | **Permission chain** on every spawn (AUTO / CHAIN / ROOT); root owner is the final authority |
| Failure isolation | A failed task marks *itself* failed; the run continues |
| State persistence | Pluggable `Backend` — `FileBackend` (JSON), `SqliteBackend` (WAL). Memory survives restarts |
| Scheduling fairness | Priority bands (`high` → `normal` → `low`) run sequentially; same-band tasks fan out concurrently |
| Governance & safety | **Constitutional cortex** — hard constraints enforced regardless of LLM output |
| Auditability | **Thought Trail** — per-task capture of every reasoning step + tool call |

This is the framing that separates a lab experiment from **infrastructure a CTO would actually trust**.

---

## 📥 Install

```bash
pip install ormica                # core (MockBrain — no LLM cost)
pip install ormica[claude]        # + Anthropic Claude (native)
pip install ormica[gemini]        # + Google Gemini (native)
pip install ormica[universal]     # + OpenAI · Ollama (local) · OpenRouter · Groq · Together · DeepSeek · vLLM · LM Studio · …
pip install ormica[all]           # everything above
```

Python 3.10+ required. **One install command, every major LLM.** See [docs/guides/llm-providers.md](./docs/guides/llm-providers.md) for the full recipe matrix.

> **Hacking on ormica itself?** The published wheel doesn't ship tests. Clone the repo and follow [CONTRIBUTING.md](./CONTRIBUTING.md):
>
> ```bash
> git clone https://github.com/Ranzim/ormica.git && cd ormica
> pip install -e ".[dev]"      # pytest, ruff, build, twine
> pytest                       # full suite in <1s
> ```

---

## 🚀 30-Second Taste

```python
from ormica import Ormica
from ormica.brain import ClaudeBrain          # or GeminiBrain · ollama_brain · UniversalBrain
from ormica.cortex import Constitution, Rule

# 1. Encode the law of the colony
constitution = Constitution([
    Rule(name="depth_cap",
         description="never grow past depth 4",
         check=lambda ctx: ctx["depth"] <= 4, stage="spawn"),
])

# 2. Seed the colony
org = Ormica("My SaaS", owner="Founder",
             constitution=constitution,
             memory_db="./acme.db")     # state survives restarts
org.plant("business")                    # 4 departments emerge under root

# 3. Queue intent (not implementation)
org.task("Reach out to 3 SMB leads", dept="sales", priority="high")
org.task("Forecast Q3 cash flow",     dept="finance")

# 4. Let the organization emerge
org.run(brain=ClaudeBrain())
```

…or from a terminal:

```bash
ormica init "My SaaS" --industry business --brain claude
ormica run --async --concurrency 5
```

Five lines from "no colony" to "running, signal-driven, governed, audited."

---

## 📡 How the Colony Behaves

### 1. The Permission Chain — *why growth is bounded*

<div align="center">
  <img src="docs/diagrams/06-permission-chain.png" alt="Permission chain sequence — sub-agent → parent → ConstitutionPolicy → dept lead → root" width="900">
</div>

A spawn request runs through `ConstitutionPolicy.allow(parent, child_name)` before any node is created. If a hard `Rule(stage="spawn")` fails, `SpawnDenied` is raised at the substrate level — no prompt-engineering required. The inner `SpawnPolicy` then handles risk: **AUTO** (parent alone), **CHAIN** (N ancestors confirm), **ROOT** (only the human owner can authorize). Configure per role with `RoleRisk({"finance": ROOT, "scout": AUTO})`. See [docs/architecture/01-hierarchy.md](./docs/architecture/01-hierarchy.md).

### 2. The Pheromone Field — *coordination without chat*

<div align="center">
  <img src="docs/diagrams/07-pheromone-field.png" alt="Pheromone field — multiple ants emit and reinforce; a single field decays lazily; another ant senses" width="900">
</div>

Three ants `emit` and `reinforce` a topic; a fourth `sense`s the resulting trail. Decay is **lazy** — `strength_at(now) = strength × 0.5^((now − last_touch) / half_life)`, computed on read, never persisted as a mutation. Reinforced trails dominate; weak trails fall below the floor and are pruned by `stigma.prune()`. The field survives process restarts when Mycelium uses `FileBackend` or `SqliteBackend`.

### 3. Agent State Topology — *every node has a known phase*

<div align="center">
  <img src="docs/diagrams/04-agent-state.png" alt="Agent state machine — IDLE → WORKING → DONE / FAILED, with PRUNED as a parallel terminal" width="900">
</div>

Every transition emits an event onto the `EventBus`. A subscribed `TraceObserver` aggregates them per `task_id` into a `Trace` — that's the **Thought Trail**, queryable later via `org.trace_for(task_id)`.

---

## 🩺 The Colony Health Report

`ormica status` — the colony's vital signs without running anything.

```text
$ ormica status

name:     My SaaS
owner:    Ranzim
industry: business
brain:    claude (model=claude-opus-4-7)

tree (5 nodes):
  - My SaaS [root]
    - operations  [operations]
    - sales       [sales]
    - marketing   [marketing]
    - finance     [finance]

tasks queued: 2
  - [high]   sales:   Reach out to 3 SMB leads
  - [normal] finance: Forecast Q3 cash flow
```

A richer dashboard — signal intensity per topic, branch depth, governance compliance, top-N pheromone trails — is on the [roadmap](#%EF%B8%8F-roadmap) as a v0.5 web UI on top of the Thought Trail.

---

## 🆚 vs. the Alternatives

| | LangChain · CrewAI · AutoGen | **Ormica** |
|---|---|---|
| Structure | Fixed chains / graphs | **Living tree** — grows to N depth |
| Agent creation | Defined upfront | **Self-spawning** on demand |
| Growth control | None built in | **Permission chain to root** (canopy) |
| Coordination | Direct messaging | **Stigmergic signals + emergence** |
| State persistence | DIY | **Pluggable `Backend`** (file / sqlite) |
| Failure handling | Often kills the run | **Failed task ≠ dead system** |
| Governance | "Try harder prompts" | **First-class `Constitution`** (cortex) |
| Auditability | Ad-hoc logging | **Thought Trail per task** (observe) |
| Focus | General purpose | **Production agent operations** |

---

## 📦 What's Inside

```
ormica/
├── arbor/         Tree · Node · Branch · SpawnPolicy       🌲 emergent hierarchy
├── canopy/        Permission chain (AUTO · CHAIN · ROOT)   🏛️ growth governance
├── mycelium/      Shared KV + FileBackend + SqliteBackend  🍄 persistent memory
├── stigma/        Pheromone trails · lazy decay            🐜 stigmergic signals
├── brain/         LLM seam: Mock · Claude · GPT            🧠 the colony's thinking
│                  (sync + async) · Router · Tool · @tool
├── cortex/        Constitution · Rule · Policy             ⚖️ law of the colony
├── observe/       Event · EventBus · TraceObserver         📡 the Thought Trail
├── colony/        AgentTemplate · Colony · YAML loader     🏢 industry templates
│                  (business + supply_chain bundled)
├── agent.py       Agent · AsyncAgent · ToolLoopExceeded
├── runtime.py     Task · TaskRunner · AsyncTaskRunner
├── core.py        Ormica facade — single import
└── cli/           ormica init / run / status / colonies
```

```
docs/                                # the onboarding map
├── README.md                         index
├── concepts.md                       Computational Stigmergy in depth
├── getting-started.md                install + hello-world
├── architecture/                     one page per module / pillar
└── guides/                           writing colonies, tools, rules, traces…
```

`tests/` — **362 tests · ~650ms · no SDK deps required for CI.**

---

## 🏗️ Architecture — under the hood

Six diagrams covering the engine's internals. Click any thumbnail for the full-resolution image.

### System architecture

How `Ormica` wires the pillars, agent layer, runtime, brain seam, and observability into one object. Use this as the import map when navigating the codebase.

<div align="center">
  <a href="docs/diagrams/01-system-architecture.png">
    <img src="docs/diagrams/01-system-architecture.png" alt="System architecture — facade, runtime, agent, five pillars, brain, colony, observe" width="880">
  </a>
</div>

### Task execution lifecycle

End-to-end path of a single `org.run()` call: queue → priority sort → target node → brain selection → `Agent.act` → `brain.think` → `Response` → side effects on the `EventBus` and `Mycelium` → `RunResult`. One LLM call per task; same-priority tasks fan out concurrently in `org.arun()` via `asyncio.gather`.

<div align="center">
  <a href="docs/diagrams/03-task-lifecycle.png">
    <img src="docs/diagrams/03-task-lifecycle.png" alt="Task execution lifecycle — inputs, TaskRunner, Agent.act, EventBus side effects, RunResult" width="900">
  </a>
</div>

### Tool-use loop (`Agent.act_with_tools`)

The ReAct iteration: `compose system prompt → brain.think → execute tool calls → append results → loop` until the model returns text or `max_iterations` is exceeded (`ToolLoopExceeded`). Every iteration emits `think.recorded` onto the bus.

<div align="center">
  <a href="docs/diagrams/05-tool-loop.png">
    <img src="docs/diagrams/05-tool-loop.png" alt="Tool-use loop — Agent.act_with_tools iteration with brain.think, tool dispatch, history append" width="720">
  </a>
</div>

### Persistence stack

`Mycelium` is the developer API surface; underneath, one of three `Backend` implementations decides what survives a restart. `Stigma` is layered on top of `Mycelium` so signals get persistence for free.

<div align="center">
  <a href="docs/diagrams/08-persistence-stack.png">
    <img src="docs/diagrams/08-persistence-stack.png" alt="Persistence stack — Developer API, Mycelium, Stigma, three pluggable backends" width="900">
  </a>
</div>

### The Thought Trail

Every reasoning step (`RUN_STARTED`, `TASK_STARTED`, `think.recorded`, `TASK_DONE`, `NODE_PRUNED`, …) is published on the `EventBus`. A `TraceObserver` indexes them by `task_id` and writes the resulting `Trace` to `mycelium['traces/{task_id}']` at task completion. The black-box problem becomes a query.

<div align="center">
  <a href="docs/diagrams/09-thought-trail.png">
    <img src="docs/diagrams/09-thought-trail.png" alt="Observability — sources publish events to EventBus; TraceObserver writes traces to Mycelium; org.trace_for retrieves" width="900">
  </a>
</div>

### Brain layer topology

The `Brain` protocol has three native adapters (Claude, Gemini, GPT) plus one `UniversalBrain` that fronts any OpenAI-compatible endpoint. The five provider helpers (`ollama_brain`, `openrouter_brain`, `groq_brain`, `together_brain`, `deepseek_brain`) are one-liners over `UniversalBrain` with the right `base_url` baked in. `MockBrain` implements the same protocol with scripted replies for offline tests; `Router` dispatches different brains per node.

<div align="center">
  <a href="docs/diagrams/10-brain-topology.png">
    <img src="docs/diagrams/10-brain-topology.png" alt="Brain layer topology — Brain protocol, native adapters, UniversalBrain, provider shortcuts, MockBrain, Router" width="900">
  </a>
</div>

---

## 🛣️ Roadmap

- [x] **v0.1** — Four pillars + runtime + CLI + persistence + async + observability *(here)*
- [ ] **v0.2** — YAML Constitutions · soft-violation events · per-node rule overrides
- [ ] **v0.3** — Async tools · streaming responses · first integrations (Gmail · Notion · GitHub · Stripe)
- [ ] **v0.4** — ChromaDB backend (semantic mycelium) · vector signals
- [ ] **v0.5** — **Colony Dashboard** (web UI) — signal intensity, branch depth, governance compliance, live Thought Trail
- [ ] **v1.0** — Ormica Cloud (hosted platform)

GitHub Project board is coming. Open an issue to vote on or contribute to any roadmap item.

---

## 🤝 Join the Colony — Contributing

The colony is young; new contributors shape its character.

### 🚀 New here? Three pages to read:

| | Page | What you'll get |
|---|---|---|
| 1 | **[Your First PR](./docs/guides/your-first-pr.md)** | The shortest path from "I want to help" to "my PR is merged." |
| 2 | **[CONTRIBUTING.md](./CONTRIBUTING.md)** | The *where-to-put-what* matrix + hard rules of the codebase. |
| 3 | **One [architecture page](./docs/architecture/README.md)** | Pick the pillar you're touching. Each page is ~5 minutes. |

### 🐜 Good first contributions

| You want to add… | Where it goes | Read first |
|---|---|---|
| 🏢 A new industry / colony | `ormica/colony/<name>/` or a YAML file | [Writing a colony](./docs/guides/writing-a-colony.md) |
| 🛠️ A new tool | wherever you use `act_with_tools(...)` | [Writing tools](./docs/guides/writing-tools.md) |
| 🧠 A new LLM provider | `ormica/brain/<provider>.py` | [Brain](./docs/architecture/03-brain.md) |
| 🍄 A persistence backend | `ormica/mycelium/<name>_backend.py` | [Persistence](./docs/guides/persistence.md) |
| 📡 A new observer (metrics, log sink) | `ormica/observe/<observer>.py` | [Observability](./docs/architecture/05-observability.md) |
| 📚 A docs improvement | `docs/` | The page itself |
| 🐛 A small bug fix | wherever the bug lives | The bug report |

### 💬 Other ways to help

- 📌 **Browse open issues** — look for [`good first issue`](https://github.com/Ranzim/ormica/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) or [`help wanted`](https://github.com/Ranzim/ormica/labels/help%20wanted).
- 💭 **Open a Discussion** — questions, ideas, show-and-tell at [GitHub Discussions](https://github.com/Ranzim/ormica/discussions).
- ⭐ **Star the repo** — visibility helps new contributors find us.
- 📣 **Share your colony** — tag the project when you build something cool.

### 🧪 Before you push

```bash
pytest              # 362 tests, ~650ms, all green
ruff check .        # lint clean
```

By participating, you agree to abide by the [Code of Conduct](./CODE_OF_CONDUCT.md). To report a security issue, see [SECURITY.md](./SECURITY.md).

---

## 🏷️ Recommended GitHub Topics

When tagging the repo (Settings → "Manage topics"):

```
ai · agents · agentic · multi-agent · multi-agent-framework
distributed-systems · stigmergy · swarm-intelligence
cybernetics · self-organization · emergence
llm · autonomous-agents · python · framework
```

Positions Ormica where it belongs: **systems engineering**, not "another AI agent chatbot."

---

## 📜 License

MIT — see [LICENSE](LICENSE). Free to use, modify, and build on.

---

<div align="center">

**Ormica** — *organize like a colony · grow like a forest · decide like an organization · audit like infrastructure.*

<sub><i>Computational Stigmergy · v0.1 · ant-colony-inspired coordination for autonomous AI operations</i></sub>

</div>
