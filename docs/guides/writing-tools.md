# Writing tools

Let agents call Python functions and get results back.

## The `@tool` decorator

```python
from ormica.brain import tool

@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Look up the current weather in a city."""
    # …your real implementation…
    return f"sunny in {city}, 22°{unit[0].upper()}"
```

That's it. The decorator inspects the type hints and docstring to build the JSON-Schema the LLM sees:

```python
get_weather.schema
# {
#   "type": "object",
#   "properties": {
#     "city": {"type": "string"},
#     "unit": {"type": "string"},
#   },
#   "required": ["city"],
# }
```

Parameters without a default become required. The first docstring line becomes the tool description.

## Supported types

| Python type hint | JSON-Schema type |
|---|---|
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `list` | `array` |
| `dict` | `object` |

For richer schemas (enums, constraints, nested objects), pass an explicit schema:

```python
from ormica.brain import Tool

book_flight = Tool(
    name="book_flight",
    description="Book a flight to a destination.",
    fn=_book_flight_impl,
    schema={
        "type": "object",
        "properties": {
            "destination": {"type": "string"},
            "date": {"type": "string", "format": "date"},
            "passengers": {"type": "integer", "enum": [1, 2, 3, 4, 5, 6, 7, 8]},
        },
        "required": ["destination", "date", "passengers"],
    },
)
```

## Using tools with an Agent

```python
from ormica import Agent
from ormica.brain import ClaudeBrain

agent = Agent(node, ClaudeBrain())
response = agent.act_with_tools(
    "What's the weather in Tokyo?",
    tools=[get_weather],
    max_iterations=8,
)
```

What `act_with_tools` does:

1. Call `brain.think(prompt, tools=[...])`.
2. If `response.wants_tools`:
   - Append an assistant message recording the tool_use blocks.
   - Execute each tool, append a tool-role message with the result.
   - Loop.
3. If `not response.wants_tools`:
   - Mark the node `DONE` and return.
4. If we hit `max_iterations` (default 8): raise `ToolLoopExceeded`.

## Failure modes (and how they recover)

| Situation | What happens |
|---|---|
| Tool raises an exception | The exception becomes a tool-result message (`"ValueError: ..."`). Model can adjust. |
| Model asks for an unknown tool | A tool message with `"unknown tool: 'x'"` is appended. Model can adjust. |
| Model keeps asking for tools forever | `ToolLoopExceeded` is raised. Node marked `FAILED`. |

The loop is designed to give the model multiple shots without crashing the run.

## Async tools

The tool function itself is sync; the **loop** has an async sibling on `AsyncAgent`:

```python
from ormica import AsyncAgent
from ormica.brain import AsyncClaudeBrain

agent = AsyncAgent(node, AsyncClaudeBrain())
response = await agent.act_with_tools("...", tools=[get_weather])
```

The agent calls `get_weather` synchronously, but `brain.think` is awaited. So you get concurrency *across* tasks (multiple agents fanning out) while individual tool calls stay sync. Native async tools is a planned follow-up — three lines in `_run_tool`.

## Best practices

- **One tool = one verb.** `get_weather`, `book_flight`, `query_db` — not `do_stuff`.
- **Type-annotate everything.** The auto-generated schema is only as precise as your hints.
- **Use the docstring for the description.** The LLM reads it to decide *when* to use the tool.
- **Validate inside the tool.** The schema gates parameter *shape*, not semantic validity ("date must be a future date").
- **Return strings.** Tool results become message content; non-string results are `str()`-ified.
- **Don't put secrets in tool args.** They land in the message history and the Thought Trail.

## Related

- [Brain architecture](../architecture/03-brain.md) — how `tools=` flows through Claude / GPT.
- [Reading the Thought Trail](./reading-the-thought-trail.md) — every tool call is captured.
