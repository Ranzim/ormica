# Live Swarm — watch the whole colony work

A busy colony that drives **every concept in the live graph at once**, so you can
watch the engine breathe in the 3D `/graph` view.

```bash
python examples/live_swarm/run.py
#   → open http://127.0.0.1:8777/graph
python examples/live_swarm/run.py --agents 60 --pace 0.35
```

No API key — an offline `MockBrain` keeps the colony busy. What you'll see:

| In the graph | Concept |
| --- | --- |
| ants **spawn** under nests, and **delegate** to sub-agent ants | `node.spawned` |
| an ant's **abdomen swells** as it forages | `think.recorded` (tokens = task load) |
| **harvests** (hexagons) brought home | think outputs |
| **pheromone** (green diamonds) laid and re-read | `memory.write` / `memory.read` |
| amber **message** pulses recruiting nestmates | `message.sent` |
| white rings + retries when an answer needs fixing | `verify.retry` / `verify.failed` |
| ants **fade and die** as spent branches are pruned | `node.pruned` (decay) |

Toggle move/rotate (top-right), drag, scroll to zoom, and click any ant to
reveal the real node and its latest output. The busiest foragers carry the
fattest abdomens — that's the "task dimension" made visible.

## Flags

| Flag | Meaning |
| --- | --- |
| `--agents N` | soft cap on colony size (it churns around this) |
| `--pace S` | seconds between beats (lower = livelier) |
| `--seed N` | RNG seed (reproducible) |
| `--ticks N` | stop after N beats (`0` = run forever) |
| `--no-serve` | run the loop headless (no dashboard) — used by the smoke test |
