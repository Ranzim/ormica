# The Evolutionary Forest

The Forest runs many colonies and votes. The Evolutionary Forest goes further:
treat each colony's `Preferences` (its cost, quality, and speed dials) as a
genome, score how well it did, keep the best, and breed the next generation by
crossover and mutation. Over a few generations the population drifts toward
strategies that actually work, discovered rather than tuned by hand.

## Usage

You give it an `evaluate(prefs)` that runs a colony with those preferences and
returns `(answer, fitness)`. Fitness is anything you can measure: did it verify,
how good was the result, how cheap. Everything else is a standard evolutionary
loop.

```python
from ormica import evolve, Ormica
from ormica.brain import GeminiBrain

def evaluate(prefs):
    org = Ormica("gen", preferences=prefs)
    answer = org.solve("Design the caching layer", brain=GeminiBrain()).content
    return answer, score(answer)        # your own scorer, 0..1

result = evolve(evaluate, generations=4, population=6, seed=0)
result.best.prefs        # the preferences that won
result.best.answer       # what that colony produced
print(result.pretty())   # best fitness per generation
```

## How breeding works

- Each generation evaluates the whole population and sorts by fitness.
- The top `survivors` carry over unchanged.
- The rest are refilled by crossing two survivors (each dial taken from one
  parent or the other) and mutating (a small gaussian jitter on each dial,
  clamped to the valid range).
- `mutation` sets the jitter size. `seed` makes a run reproducible. `base` lets
  you seed the first generation with preferences you already trust.

## When it is worth it

Evolution costs `generations * population` colony runs, so it fits offline tuning
of a strategy you will reuse many times, not a one-off request. Pair it with a
cheap, deterministic scorer during search, then run the winning `Preferences` in
production.

See `ormica/evolution.py`.
