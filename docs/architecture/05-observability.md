# Pillar 4 — Observability & Traceability

**Module:** `observe`
**Solves:** the *Black Box* problem. Every reasoning step is captured, queryable, and tied back to the task that triggered it.

## What it is

Two layers:

1. **Events** — a pub/sub bus on every `Ormica` instance. Runners emit `task.started` / `task.done` / `task.failed` / `run.started` / `run.completed` / `think.recorded`. Observers consume.
2. **Thought Trail** — for any task you ran, you can ask the org "what did the agent think?". That returns a `Trace` with one `TraceEntry` per `Brain.think` call: messages, system prompt, tool names, response text, tool calls, tokens used.

## The event bus

```python
from ormica.observe import LogObserver, CounterObserver, CollectObserver

org.subscribe(LogObserver())                # streams events to stderr
metrics = CounterObserver(); org.subscribe(metrics)
collector = CollectObserver(); org.subscribe(collector)

org.run(brain=MockBrain(replies=["ok"]))

metrics.get("task.done")                    # → N
metrics.get("task.failed")                  # → N
collector.of_type("task.done")              # → list[Event]
```

| Type | Where | Role |
|---|---|---|
| `Event` | [`ormica/observe/event.py`](../../ormica/observe/event.py) | `type` · `timestamp` · `source` · `payload` |
| `EventBus` | [`ormica/observe/bus.py`](../../ormica/observe/bus.py) | subscribe / unsubscribe / emit |
| `Observer` (Protocol) | [`ormica/observe/observer.py`](../../ormica/observe/observer.py) | one method: `notify(event)` |
| `LogObserver` | [`ormica/observe/observer.py`](../../ormica/observe/observer.py) | streams one line per event |
| `CounterObserver` | [`ormica/observe/observer.py`](../../ormica/observe/observer.py) | running counts by event type |
| `CollectObserver` | [`ormica/observe/observer.py`](../../ormica/observe/observer.py) | stores events; filter by type |

### Canonical event types

| Constant | When |
|---|---|
| `RUN_STARTED` | A run loop begins |
| `RUN_COMPLETED` | A run loop ends |
| `TASK_STARTED` | One task moves from pending → running |
| `TASK_DONE` | A task succeeded |
| `TASK_FAILED` | A task threw |
| `THINK_RECORDED` | A `Brain.think` call completed (used by Thought Trail) |

A bad observer can never kill the bus — exceptions in `notify` are swallowed. Observability is a side concern.

## The Thought Trail

```python
from ormica.observe import TraceObserver

trail = TraceObserver(store=org.memory)     # persists to mycelium under traces/{id}
org.subscribe(trail)
org.run(brain=ClaudeBrain())

trace = org.trace_for(task_id)
trace.status                                # "done" / "failed"
for entry in trace.entries:
    print(entry.response_content, entry.tokens_used)
    for call in entry.response_tool_calls:
        print(f"  called {call['name']} with {call['arguments']}")
```

| Type | Where | Role |
|---|---|---|
| `TraceEntry` | [`ormica/observe/trace.py`](../../ormica/observe/trace.py) | One think call: messages · system · tool_names · response_content · response_tool_calls · tokens_used · finish_reason |
| `Trace` | [`ormica/observe/trace.py`](../../ormica/observe/trace.py) | task_id · node_id · target · description · status · started_at · ended_at · entries |
| `TraceObserver` | [`ormica/observe/trace.py`](../../ormica/observe/trace.py) | Subscribes to the bus; stitches per-task traces; persists to mycelium |
| `emit_think_event` | [`ormica/observe/trace.py`](../../ormica/observe/trace.py) | Called by Agent after each think; the bridge |

`org.trace_for(task_id)` reads from mycelium first (so traces survive process restarts when you use `SqliteBackend` or `FileBackend`), then falls back to any in-memory `TraceObserver` currently subscribed.

See [Reading the Thought Trail](../guides/reading-the-thought-trail.md) for the full debugging pattern.

## Where think-recording happens

Inside `_AgentBase`:

```python
# ormica/agent.py
self._record_think(messages, system, tools, response)
```

Both `Agent.act` and `Agent.act_with_tools` call this after each `Brain.think` (sync and async variants). The runners set `agent.events = org.events` and `agent.task_id = task.id` before calling — so the trace knows which task owns the event.

## Events vs signals — different abstractions

| | Events (observe) | Signals (stigma) |
|---|---|---|
| Direction | One-way pub/sub | Read/write field |
| Purpose | Audit, debugging, metrics | Agent coordination |
| Persistence | Optional (TraceObserver → mycelium) | Always via mycelium |
| Decay | None | Exponential half-life |
| Typical consumer | Humans, dashboards, log sinks | Other agents |

Don't use events for coordination, and don't use signals for audit — they look similar but their consumers are different.

## What's deliberately *not* in this module

- **No async `Observer.notify`.** Sync only. Observers should be cheap; if you need to ship events to a remote sink, queue in `notify` and flush elsewhere.
- **No OpenTelemetry / Prometheus bridges.** Those are integrations; `observe` provides the seam.
- **No filtering at the bus.** Subscribers get every event; filter inside your observer.
- **No spawn / signal events** (yet). Task lifecycle covers 95% of debugging needs. Adding `signal.emitted` is a one-line addition when needed.

## Related

- [Reading the Thought Trail](../guides/reading-the-thought-trail.md) — the debugger's perspective.
- [Persistence](../guides/persistence.md) — `SqliteBackend` makes traces survive across runs.
