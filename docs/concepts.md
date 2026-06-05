# Concepts

Ormica fuses three ideas — and adds a fourth layer to make them production-safe. Understanding them explains every design decision.

## 1. Ant colony intelligence (stigmergy)

Ants have no boss. Yet food gets found, paths get optimized, the colony thrives. They coordinate through **stigmergy** — leaving signals (pheromones) in the environment that other ants detect and reinforce. Strong trails dominate; weak ones evaporate.

In Ormica, agents leave **signals** in shared memory (`mycelium`). Other agents detect and reinforce them. The `stigma` module handles this. Coordination emerges without central commands.

## 2. Random forest structure

A random forest isn't one decision tree — it's many trees, each growing its own branches from a different angle, voting together. The diversity is the intelligence.

In Ormica, a problem can be explored by multiple branches in parallel, each growing to whatever depth it needs (`arbor`). No fixed structure — the tree grows to fit the problem.

## 3. Organizational theory

Real organizations control growth through hierarchy. You don't hire someone without approval rising up the chain. This prevents chaos.

In Ormica, spawning a new agent requires permission that **propagates up the tree** to the root owner (`canopy`). Three risk levels — AUTO, CHAIN, ROOT — decide how far up a request must travel. This solves the "infinite agent explosion" problem.

## How they combine

```
A problem enters at the root.
Branches explore it in parallel (random forest).
Agents signal findings to each other (ant colony).
When an agent needs help, it requests permission to spawn (organization).
Weak branches are pruned; strong paths are reinforced.
A result emerges — and flows back to the owner.
```

The result is a system that is **alive** (it grows organically) but **controlled** (every agent is known and approved by root).

## 4. Constitutional governance + Thought Trail

The three biological ideas above are the *spark*. To make a colony **production-safe**, Ormica adds:

- **Constitution** (`cortex/`) — hard constraints and soft policies encoded in a `Constitution`. Where the **brain** generates a response, the **cortex** decides whether it's permissible. Token caps, role-specific blocks, depth limits — all expressed as `Rule` objects with a predicate and a stage (`pre` / `post` / `spawn`).
- **Thought Trail** (`observe/`) — every `Brain.think` call is captured by a `TraceObserver`: the messages going in, the tool calls, the response, the tokens used. Tied back to a task id, queryable via `org.trace_for(id)`, optionally persisted to mycelium.

Together they answer the two questions that block AI from real business operations:
- *"How do I stop the agent from doing X?"* → put it in the Constitution.
- *"Why did the agent do Y?"* → read the Thought Trail.

That's what separates a lab experiment from infrastructure a CTO would actually trust.

## How to read this codebase

The four pillars map directly onto modules. See [`architecture/README.md`](./architecture/README.md) for the full map and reading order.
