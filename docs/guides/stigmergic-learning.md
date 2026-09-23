# Stigmergic learning

Pheromone signals decay on their own. Stigmergic learning closes the other half
of the loop, the part that makes an ant colony smart: when a choice leads to a
good outcome, lay down stronger pheromone on it. Over many runs the colony
converges on the choices that work, and because trails still decay, it forgets
advice that stops paying off. This is Ant Colony Optimization, applied to agent
workflows.

The decision worth learning is usually **routing**: of several agents that could
take a task of some kind, which one actually produces verified, cheap answers?
Nobody assigns that. The colony discovers it, and grows emergent specialists.

## The router

```python
from ormica import route_reward

router = org.stigmergic_router()

node = router.select("billing-question", candidates=["alice", "bob", "carol"])
# ... run the task on `node`, get a finished Task back ...
router.reinforce("billing-question", node, route_reward(task))
```

- `select(kind, candidates)` samples a candidate, weighted by learned pheromone,
  with exploration so nothing is ruled out too early.
- `reinforce(kind, choice, reward)` rewards what worked. A reward of zero lays
  nothing, so a bad choice just lets its trail fade.
- `route_reward(task)` is zero unless the task verified, and higher the cheaper a
  verified one was. The objective is correct and cheap.
- `best(kind, candidates)` and `preferences(kind, candidates)` read out what the
  colony has learned.

## Ambient learning with dispatch

If you do not want to wire the router by hand, `org.dispatch` does the whole loop
for you: it routes a task to the learned best candidate for its kind, runs it,
and reinforces from the real outcome. Call it repeatedly and the colony gets
better at your work on its own.

```python
org.dispatch("Summarize this week's numbers", kind="report",
             candidates=["alice", "bob", "carol"], brain=brain)
```

The dashboard has a **learning** page that shows, per kind, which agent the
colony now prefers and how strong that preference is. Watch the specialists
emerge as you use it.

## It learns your whole strategy, not just routing

The router works over any `(kind, candidates)` pair, so the same call learns the
best **tool** or the best **decomposition** for a kind of task. Point it at tool
names or plan names and reward the outcomes.

## Staying robust

Cumulative pheromone couples quality with how often a choice is tried, so a very
greedy setup can lock onto whatever it happens to try first. The router guards
against that by default: an exploration floor (`epsilon`) keeps every option in
play, and a trail ceiling (`max_strength`) stops any one option running away. In
real runs, pheromone decay does the rest as time passes between tasks. If you
want to tune it, `temperature` controls how sharp selection is, and `explore`
sets the baseline weight for untried options.

## Persistence

Give the colony a persistent backend (`memory_db=` or `memory_path=`) and the
learning survives restarts. The specialist a colony discovered yesterday is still
its specialist tomorrow.

See [`examples/learning`](../../examples/learning) and
[`examples/learning_strategy`](../../examples/learning_strategy).
