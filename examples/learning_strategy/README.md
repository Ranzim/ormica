# Learn the whole strategy, not just the router

Stigmergic learning is not only for picking an agent. A `StigmergicRouter` learns
over any `(kind, candidates)` pair, so the same mechanism learns:

- which **tool** solves a kind of task best, and
- which **decomposition** (plan shape) solves a kind of goal best.

```bash
python examples/learning_strategy/run.py
```

Offline and deterministic. Two learners run side by side and each converges on
the genuinely best option, discovered from rewards rather than assigned:

```
learned best tool: regex
learned best plan: map-reduce
```

The point: agent, tool, and decomposition are all just decisions, and the colony
can learn all three from what actually verifies. Reward correct and cheap
outcomes (see `route_reward`), and over time the colony optimizes its own
strategy end to end.

A note on tuning. Cumulative pheromone couples quality with how often a choice is
tried, so a very sharp, no-exploration setup can lock onto whatever it happens to
try first. Softer selection (higher `temperature`, more `explore`) and pheromone
decay over time keep it honest. In real runs, decay happens naturally as time
passes between tasks.
