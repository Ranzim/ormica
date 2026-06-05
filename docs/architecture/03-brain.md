# Brain — the pluggable thinking engine

**Module:** `brain`
**Role:** every agent thinks through a `Brain`. Swap providers without changing agent logic.

> **Note on naming.** This module used to be called `cortex`. The pitch reserves "cortex" for the colony's governance layer ([Pillar 3](./04-governance.md)), so the LLM seam is now `brain`. Brain *generates*; cortex *constrains*.

## The protocol

`Brain` is one method:

```python
class Brain(Protocol):
    name: str
    def think(
        self,
        prompt: str | list[Message],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        tools: list[Tool] | None = None,
    ) -> Response: ...
```

The async sibling `AsyncBrain` is identical but `async def think(...)`. Same protocol, different I/O.

## Built-in implementations

| Class | Where | When to use |
|---|---|---|
| `MockBrain` | [`ormica/brain/mock.py`](../../ormica/brain/mock.py) | Tests; scripted demos. Replies can be plain strings or `ToolCall` lists. |
| `ClaudeBrain` | [`ormica/brain/claude.py`](../../ormica/brain/claude.py) | Anthropic SDK. Behind `pip install ormica[claude]`. |
| `GPTBrain` | [`ormica/brain/gpt.py`](../../ormica/brain/gpt.py) | OpenAI SDK. Behind `pip install ormica[openai]`. |
| `AsyncMockBrain` / `AsyncClaudeBrain` / `AsyncGPTBrain` | same files | Async siblings of each, for `org.arun(...)`. |

All adapters are **thin**: they map our `Message` / `Response` types onto the provider's wire format. No streaming, no temperature, no sampling parameters — those are caller-side concerns (and on Opus 4.7 the sampling params 400).

## Routing — one brain per node

```python
from ormica.brain import ClaudeBrain, GPTBrain, Router

router = Router(
    default=GPTBrain(model="gpt-4o-mini"),               # cheap scouts
    by_role={"executive": ClaudeBrain(model="claude-opus-4-7")},
)
org.run(brain=router)
```

A `Router` picks a brain for each node based on (in order): `by_name`, `by_role`, `default`.

## Tools

Brain accepts an optional `tools=[Tool, ...]` list. When the model returns `tool_calls`, the harness executes the matching Python function and feeds the result back in a `tool` message.

```python
from ormica.brain import tool

@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Look up current weather in a city."""
    return f"sunny in {city}"

agent.act_with_tools("How's it in SF?", tools=[get_weather])
```

See [Writing tools](../guides/writing-tools.md) for the full pattern.

## TokenBudget

Lightweight accounting object. Pass to `Agent(budget=...)` and the runtime consumes tokens after each `think`:

```python
from ormica.brain import TokenBudget, BudgetExhausted

budget = TokenBudget(limit=100_000)
# … agents use it …
if budget.exhausted:
    raise BudgetExhausted()
```

Budgets are also visible from inside a `Constitution` rule — useful for "spend less than X tokens per task" enforcement.

## What's deliberately *not* in this module

- **No streaming.** Sync round trip per `think`. A future `AsyncStreamingBrain` is the natural place to add it.
- **No prompt caching.** The caching strategy depends on the *caller's* workload; the adapter is too thin to decide.
- **No function-calling beyond the basic loop.** No parallel tool calls, no tool_choice forcing, no JSON-mode toggling. Add when a real use case appears.
- **No retries.** The Anthropic / OpenAI SDKs retry on their own; on top of that, `org.run` marks individual task failures as `failed` and continues.

## Related

- [Writing tools](../guides/writing-tools.md) — `@tool` + the act-with-tools loop.
- [Async + Router](../guides/async-and-routing.md) — mixing providers per node.
- [Pillar 3 — Governance](./04-governance.md) — checking brain output against a Constitution.
