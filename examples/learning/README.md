# Learning Lab — a colony that discovers its own specialist

This is the demo for Ormica's most distinctive idea: **stigmergic learning**. A
colony that gets better the more it runs, with no training loop and no labels
beyond "did the answer verify".

Three analysts can take the same kind of task. Nobody says who is good at it. A
**stigmergic router** picks one for each task, rewards outcomes that verified and
were cheap, and lays pheromone on what worked. Because pheromone also decays,
stale advice fades and the colony keeps re-checking. This is Ant Colony
Optimization, applied to agent workflows.

```bash
python examples/learning/run.py
python examples/learning/run.py --rounds 120
```

Offline and deterministic (MockBrains, seeded), so no key is needed. Sample run:

```
learning curve (share routed to the specialist 'ace' per window):
  rounds   0-9    █████████████████        70%
  rounds  10-19   ████████████████████████ 100%
  ...
learned preference (pheromone strength):
  ace        56.89
  novice-1   0.00
  novice-2   0.00

the colony discovered its specialist: ace
```

The colony explores at first, then converges on the analyst that actually
produces verified, cheap answers. The losers earn no pheromone, so their trails
never grow. Nothing was hard coded; the specialist was **discovered**.

## The idea in code

```python
router = org.stigmergic_router()

node = router.select("estimate", ["ace", "novice-1", "novice-2"])
# ... run the task on `node` ...
router.reinforce("estimate", node, route_reward(task))   # reward correct + cheap
```

- `select` samples a candidate weighted by learned pheromone, with exploration
  so nothing is ruled out too early.
- `route_reward(task)` is 0 for a task that did not verify, and higher the
  cheaper a verified one was. Correct **and** cheap wins.
- Give the colony a persistent backend and the learning survives restarts. Over
  time you get **emergent specialists**: the ant that keeps solving a kind of
  problem keeps getting that kind of problem.

See `ormica/learning.py` for the router.
