# Architecture overview

Ormica is built on **four functional pillars** plus a small runtime layer that stitches them together. Each pillar exists for one reason and exposes one minimal API.

## The four pillars

```
┌──────────────────────────────────────────────────────────────────────┐
│  PILLAR 4 — Observability    observe/    events · Thought Trail      │
├──────────────────────────────────────────────────────────────────────┤
│  PILLAR 3 — Governance        cortex/     Constitution · Rule        │
├──────────────────────────────────────────────────────────────────────┤
│  RUNTIME                      agent.py · runtime.py                  │
│                               Agent · Task · Runner · async          │
├──────────────────────────────────────────────────────────────────────┤
│  THINKING                     brain/      Brain · Tool · Router      │
├──────────────────────────────────────────────────────────────────────┤
│  PILLAR 2 — Signaling         stigma/ · mycelium/                    │
│                               pheromones · decay · shared memory     │
├──────────────────────────────────────────────────────────────────────┤
│  PILLAR 1 — Hierarchy         arbor/ · canopy/                       │
│                               tree · spawn permission chain          │
└──────────────────────────────────────────────────────────────────────┘
```

| # | Pillar | Role | Modules | Doc |
|---|---|---|---|---|
| 1 | **Hierarchical Structure** | Bound context. Every agent has a clear scope and a reporting line. | `arbor` · `canopy` | [01-hierarchy](./01-hierarchy.md) |
| 2 | **Stigmergic Signaling** | Indirect coordination. Strong trails dominate; weak ones evaporate. | `mycelium` · `stigma` | [02-signaling](./02-signaling.md) |
| 3 | **Constitutional Governance** | Hard constraints on what agents may do. The colony's law. | `cortex` | [04-governance](./04-governance.md) |
| 4 | **Observability** | The Thought Trail — every reasoning step is captured and queryable. | `observe` | [05-observability](./05-observability.md) |

## The runtime layer

| Concept | Doc |
|---|---|
| **Brain** — the pluggable LLM (Claude, GPT, Mock) | [03-brain](./03-brain.md) |
| **Colony** — industry templates (Python + YAML) | [06-colony](./06-colony.md) |
| **Agent · Task · Runner** — sync and async execution | [07-runtime](./07-runtime.md) |
| **Ormica facade** — the one-import entry point | [08-facade](./08-facade.md) |

## Why these names

Every module name matches the biological metaphor of its actual function:

| Module | Metaphor | Role |
|---|---|---|
| `arbor` | tree | grows the hierarchy |
| `canopy` | forest canopy controlling light | gates growth (permission chain) |
| `mycelium` | underground fungal network | shared memory layer |
| `stigma` | ant pheromones (stigmergy) | signal-based coordination |
| `brain` | cerebrum — bulk of neural processing | LLM thinking engine |
| `cortex` | cerebral cortex — executive control | rules / constitution / governance |
| `colony` | living community of agents | industry-specific templates |
| `observe` | nervous system — signals from anywhere | events + Thought Trail |

The `brain` / `cortex` split is deliberate: **brain *generates* responses; cortex *constrains* what's permissible.** They're separate layers, both biologically and architecturally.

## Design invariants

These rules apply everywhere in the codebase:

1. **Core stays industry-agnostic.** `arbor` / `canopy` / `mycelium` / `stigma` know nothing about business, healthcare, or any specific domain. Industries plug in via `colony`.
2. **Brain doesn't decide policy, cortex does.** The brain produces a candidate response; cortex's `Constitution` decides whether it's allowed.
3. **One bad observer can't kill a run.** Observability is a side concern. Exceptions in `Observer.notify` are swallowed.
4. **Failures don't abort a run.** A single failed task marks itself `failed` and the loop continues.
5. **Async is additive, not a replacement.** Sync `Brain` / `Agent` / `TaskRunner` live alongside async siblings; users pick.
6. **Persistence is a `Backend`, not a code change.** Adding sqlite or chromadb or s3 is a new `Backend` impl; `Mycelium` doesn't change.

## What to read next

- New to the codebase? → [Pillar 1: Hierarchy](./01-hierarchy.md)
- Want to write a custom industry? → [Pillar 3: Colony](./06-colony.md) + [Writing a colony](../guides/writing-a-colony.md)
- Want to enforce constraints? → [Pillar 3: Governance](./04-governance.md) + [Writing a Constitution](../guides/writing-a-constitution.md)
- Want to debug an agent? → [Pillar 4: Observability](./05-observability.md) + [Thought Trail guide](../guides/reading-the-thought-trail.md)
