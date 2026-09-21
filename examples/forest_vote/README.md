# Forest — robustness by consensus

One analyst is unreliable — right *most* of the time, but not always. A
**Forest** grows many independent colonies, lets each attempt the same question,
and takes the **majority vote**. The wrong answers get outvoted; the right one
*emerges* from agreement. This is the "grow like a forest" half of Ormica —
ensemble reliability, the same idea as LLM self-consistency (sample N times,
keep the consensus).

```
   ┌── tree 0 ──▶ 42        ┐
   ├── tree 1 ──▶ 42        │
   ├── tree 2 ──▶ 41  ✗     ├──▶  majority_vote  ──▶  42   (71% agreement)
   ├── tree 3 ──▶ 41  ✗     │
   ├── tree 4 ──▶ 42        │
   ├── tree 5 ──▶ 42        │
   └── tree 6 ──▶ 42        ┘
   no tree is authoritative — the answer is what the population converges on
```

## Run it

```bash
python examples/forest_vote/run.py
python examples/forest_vote/run.py --trees 11 --accuracy 0.55
```

No API key needed — a `MockBrain` is "correct" `--accuracy` of the time (seeded,
so the run is reproducible). Sample output:

```
individual answers: 42, 42, 41, 41, 42, 42, 42

consensus=True agreement=71% (7 trees)
   5x  '42'
   2x  '41'

consensus answer : 42   (✓ correct, 71% agreement)
2/7 individual trees were wrong — the vote held.
```

Lower `--accuracy` or `--trees` to watch the vote get shakier — the same
bias-variance trade-off as any ensemble.

## How it works

```python
from ormica import Forest, Ormica

forest = Forest(lambda: Ormica("tree"), size=7)   # a fresh colony per tree
result = forest.solve("What is 6 * 7?", brain=brain)

result.answer       # "42" — the plurality answer
result.agreement    # 0.71 — fraction of trees that agreed
result.consensus    # True — cleared the threshold with a clear winner
result.votes        # [Vote("42", 5, ...), Vote("41", 2, ...)]
```

- **Independence.** `build()` returns a *fresh* `Ormica` per tree (own tree,
  memory, signals), so attempts don't contaminate each other.
- **Voting, not authority.** `reconcile` (default `majority_vote`) picks the
  plurality; swap in `unanimous`, or `majority_vote(key=…, threshold=…)` to
  group answers by meaning or raise the consensus bar.
- **Concurrency.** Use `await forest.asolve(...)` to run the attempts in
  parallel (in threads — a sync brain parallelizes without an async brain).

Pair it with grounding: let each colony **verify** its own answer, and the
Forest votes on already-checked results — two independent layers of reliability.

See [`docs/guides/forest-voting.md`](../../docs/guides/forest-voting.md) for the
full guide.
