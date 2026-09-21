# The Forest — consensus across colonies

A single colony grows one tree to solve a goal. A **Forest** grows *many* —
independent colonies that each attempt the same goal, with their answers
reconciled by **voting**. No tree is authoritative; the answer emerges from
agreement across independent attempts. It's the ensemble / self-consistency
pattern: sample N times, keep the consensus, and you beat any single sample.

## The idea

```
   build() ─▶ colony 0 ─▶ attempt ─▶ answer ┐
   build() ─▶ colony 1 ─▶ attempt ─▶ answer ├─▶ reconcile ─▶ ForestResult
   build() ─▶ colony N ─▶ attempt ─▶ answer ┘   (majority vote)
```

Each colony is **fresh and independent** (its own tree, memory, and signals), so
attempts don't contaminate one another — the whole point of an ensemble.

## Quick start

```python
from ormica import Forest, Ormica

forest = Forest(lambda: Ormica("tree"), size=5)
result = forest.solve("What is 6 * 7?", brain=brain)

result.answer       # the consensus answer
result.agreement    # fraction of trees that agreed (0..1)
result.consensus    # did the winner clear the threshold, with no tie?
result.votes        # [Vote(answer, count, voters), ...] most-voted first
print(result.pretty())
```

Run the attempts concurrently (they're independent, usually I/O-bound):

```python
result = await forest.asolve("What is 6 * 7?", brain=brain, concurrency=5)
```

`asolve` runs each attempt in a worker thread, so a plain **sync** brain
parallelizes — no async brain required.

## Reconciliation

The default is `majority_vote`: the plurality answer wins, and `consensus` is
`True` only when that winner clears a `threshold` (default `0.5`) with no tie.

```python
from ormica import majority_vote, unanimous

Forest(build, size=5, reconcile=unanimous)                       # all must agree
Forest(build, size=5,
       reconcile=lambda a: majority_vote(a, threshold=0.7))      # 70% bar
```

**Group by meaning with `key`.** Two answers count as "the same" when their
`key` matches — essential when raw text differs but the meaning doesn't:

```python
import re
num = lambda a: (re.search(r"-?\d+", a) or [a])[0]        # compare the number
Forest(build, size=5, reconcile=lambda a: majority_vote(a, key=num))
```

For [typed artifacts](./dag-execution.md), vote on the data:

```python
majority_vote(answers, key=lambda a: a.data)
```

Unhashable answers (dicts, artifacts) are handled automatically via a stable
JSON key; the winning *raw* answer is what you get back.

## Choosing what each tree does

`attempt(org, goal, brain) -> answer` runs one tree. The default has the root
agent answer directly. Swap it to use the whole engine per tree:

```python
# each tree recursively delegates (see recursive delegation)
Forest(build, size=5, attempt=lambda org, goal, brain: org.solve(goal, brain=brain))

# each tree runs a tool-using agent, a task queue, a sandbox-grounded solve, …
```

## Compose with grounding

The Forest reduces *variance*; [grounding](./verification.md) reduces *error*.
Use both: let each colony **verify** its own answer (run the code, check a
schema, ask a judge), so the Forest votes on answers that already passed a
correctness check — two independent layers of reliability.

## When to reach for a Forest

- The task is **noisy** — the model is right often but not always.
- Getting it wrong is **expensive**, and you can afford N attempts.
- You want a **confidence signal**: `agreement` tells you how sure the
  population is, not just what it picked.

For a one-shot, cheap, or already-reliable task, a single colony is enough.

## Related

- [Recursive delegation](../../README.md#-beyond-the-four-pillars--from-coordination-to-completion) — what one tree can do before it votes
- [Verification & grounding](./verification.md) — reduce error inside each tree
- [`examples/forest_vote`](../../examples/forest_vote) — a runnable demo
