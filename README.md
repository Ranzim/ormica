<div align="center">

# 🐜 Ormica
### An Autonomous Coordination Engine
> **Seed the colony. Let the organization emerge.**

[![PyPI](https://img.shields.io/pypi/v/ormica.svg)](https://pypi.org/project/ormica/)
[![CI](https://github.com/Ranzim/ormica/actions/workflows/ci.yml/badge.svg)](https://github.com/Ranzim/ormica/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Ranzim/ormica/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/Ranzim/ormica/security/code-scanning)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

</div>

Ormica is an open-source Python framework for building **self-organizing colonies of AI agents**. You seed a goal; the colony **spawns** the agents it needs, **coordinates** them through a shared signal field, **governs** their growth, **verifies** their work, and leaves a full **audit trail** — then prunes what it no longer needs. It's model-agnostic (Claude · Gemini · OpenAI · local Ollama · …) and runs anywhere, from a laptop to many machines.

---

## ⚡ Quickstart — 30 seconds

```bash
pip install ormica
ormica doctor                                # what's installed / which keys are set
ormica ask "What is 6 * 7?" --brain gemini   # one prompt → a real answer
```

```python
from ormica import Ormica
from ormica.brain import GeminiBrain          # or ClaudeBrain · ollama_brain · UniversalBrain

# one governed call
org = Ormica("Acme")
print(org.ask("Draft a one-line launch tweet for a dev tool", brain=GeminiBrain()))

# …or a real colony that plans, runs, and governs itself (state survives restarts)
org = Ormica("My SaaS", memory_db="./acme.db")
org.plant("business")                                 # departments emerge under root
org.task("Reach out to 3 SMB leads", dept="sales", priority="high")
org.run(brain=GeminiBrain())
```

**Reach for Ormica when** you want *many* agents coordinating on real work — planning, delegating, verifying — with governance, cost caps, retries, persistence, and an audit trail around your LLMs. **Don't bother when** you just need a single answer — call the model (or `ormica ask`).

> An assistant *does a task* for you, interactively. Ormica is the **library you build on** so your software runs governed, multi-agent work **autonomously** — on your models, at your scale.

---

## 🧬 The idea — *Computational Stigmergy*

Ants build without a boss. No ant holds the plan; each responds to **pheromone trails** left in the shared environment. Ormica applies that to software — four pillars, one coherent model:

| Pillar | Module | What it does |
|---|---|---|
| 🌲 **Emergent hierarchy** | `arbor` | You define goals; the framework *grows the tree*. Agents spawn on demand, prune when done. No fixed chains. |
| 🐜 **Stigmergic coordination** | `stigma` + `mycelium` | Agents post progress to a shared **pheromone field** that decays over time; others follow strong trails. Coordination without brittle message-passing. |
| 🏛️ **Permission chain** | `canopy` | Every spawn passes a gate — `AUTO` / `CHAIN` / `ROOT`. High-risk growth escalates to the human. Growth stays bounded. |
| ⚖️ **Constitutional governance** | `cortex` | Hard/soft `Rule`s bind what agents may do, *regardless of what the model says*. The brain acts; the cortex inhibits. |

Every step — spawn, think, signal, prune — is captured on an `EventBus` and indexed into a per-task **Thought Trail** (`observe`), queryable with `org.trace_for(task_id)`. The black-box problem becomes a query.

📖 Deep dive: [docs/concepts.md](./docs/concepts.md) · [architecture pages](./docs/architecture/README.md)

---

## 🧰 What you get

| Capability | |
|---|---|
| **Recursive delegation** | an agent too small for a task spawns sub-agents that can delegate further (`org.solve`) |
| **Verify & grounding** | check an answer against a real oracle (run the code, validate a schema, ask a judge) and **retry until it's right** |
| **Typed artifacts** | schema-checked structured results that flow between tasks as data, not prose |
| **Preferences** | declare an objective — `cost` / `quality` / `speed` — and the colony biases how it decomposes, verifies, parallelises |
| **Self-healing** | task retries + circuit breaker + dead-letter, and failure-driven prune/respawn/re-route |
| **Persistence & scale** | pluggable memory (file / SQLite / vector), durable/resumable runs, and **distributed workers** draining one shared queue |
| **Speed & cost** | `CachingBrain` memoizes identical calls; a run report surfaces tokens + time |
| **Safety** | sandboxed code execution · human approval gates · secret redaction in traces |
| **Observability** | the Thought Trail + a dependency-free **live 3D dashboard** (`serve(org)` → `/graph`) |
| **Model-agnostic** | Claude · Gemini · OpenAI + one `UniversalBrain` for Ollama / OpenRouter / Groq / Together / DeepSeek / vLLM / … |

---

## 🔬 Runnable examples

| Example | Shows |
|---|---|
| [`compute_lab`](./examples/compute_lab) | answers **verified by running them** in the sandbox, watchable in the dashboard |
| [`architect`](./examples/architect) | a colony of specialists designs a **real software architecture** (typed + grounded) |
| [`distributed_colony`](./examples/distributed_colony) | many worker processes drain **one shared queue**, no dispatcher |
| [`forest_vote`](./examples/forest_vote) | many independent colonies **vote** on one goal (consensus beats a single try) |
| [`live_swarm`](./examples/live_swarm) | a self-growing colony driving every graph concept at once |

---

## 🆚 How it compares

| | LangChain · CrewAI · AutoGen | **Ormica** |
|---|---|---|
| Structure | Fixed chains / graphs | **Living tree** — grows to N depth, prunes |
| Agents | Defined upfront | **Self-spawning** on demand |
| Coordination | Direct messaging | **Stigmergic signals + emergence** |
| Growth control | None built in | **Permission chain to the human** |
| Governance | "Try harder prompts" | **First-class `Constitution`** |
| Failure | Often kills the run | **Self-healing; a failed task ≠ a dead system** |
| Auditability | Ad-hoc logs | **Thought Trail per task** |

---

## 📥 Install

```bash
pip install ormica                # core (MockBrain — no LLM cost)
pip install ormica[gemini]        # + Google Gemini
pip install ormica[claude]        # + Anthropic Claude
pip install ormica[universal]     # + OpenAI · Ollama · OpenRouter · Groq · Together · DeepSeek · …
pip install ormica[all]           # everything
```

Python 3.10+. One install, every major LLM — see [the provider matrix](./docs/guides/llm-providers.md).

Hacking on Ormica itself? `git clone`, then `pip install -e ".[dev]"` and `pytest` (**920+ tests, <2s, no API keys needed**). Details in [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## 📚 Docs

- [Getting started](./docs/getting-started.md) — install + first colony
- [Concepts](./docs/concepts.md) — Computational Stigmergy in depth
- [Guides](./docs/README.md) — colonies · tools · constitutions · verification · distributed · the Forest · dashboard
- [Architecture](./docs/architecture/README.md) — one page per module
- [CLI reference](./docs/reference/cli.md) — `init · run · resume · worker · ask · solve · plan · doctor · …`

---

## 🛣️ Roadmap

- [x] **v0.1–0.3** — four pillars · runtime · CLI · persistence · async · YAML Constitutions · semantic memory · verify/grounding · planner + DAG · durable runs · sandbox · approvals · live 3D dashboard
- [x] **v0.4–0.6** — recursive delegation · `RetryingBrain` · grounding framework · auto-RAG · async tools · typed artifacts · persistent agent tree
- [x] **v0.7–0.8** — **distributed execution** (atomic-lease workers) · the **Forest** (multi-tree voting)
- [x] **v0.9–0.10** — universe live-view · `org.ask`/`agent` ergonomics · **Preferences** · **self-healing** · `CachingBrain` · secret redaction · full CLI
- [ ] **next** — streaming responses · more integrations (Gmail · Notion · Stripe) · vector signals
- [ ] **v1.0** — hardening for high-scale production

---

## 🤝 Contributing

The colony is young; new contributors shape its character. Start with **[Your First PR](./docs/guides/your-first-pr.md)**, then [CONTRIBUTING.md](./CONTRIBUTING.md) (the where-to-put-what matrix). Before you push: `pytest` and `ruff check .`. Be kind — see the [Code of Conduct](./CODE_OF_CONDUCT.md). Security issues: [SECURITY.md](./SECURITY.md).

---

## 📜 License

MIT — see [LICENSE](LICENSE). Free to use, modify, and build on.

<div align="center">
<sub><i>Computational Stigmergy · ant-colony-inspired coordination for autonomous AI operations</i></sub>
</div>
