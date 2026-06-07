# Reading the Thought Trail

Debug an agent's reasoning: every `think` call, the prompts that went in, the response that came out, and the tools that were called.

## Setup

```python
from ormica import Ormica
from ormica.observe import TraceObserver

org = Ormica("Acme", memory_db="./acme.db")    # SqliteBackend → traces survive restarts
trail = TraceObserver(store=org.memory)         # also persists to mycelium
org.subscribe(trail)

org.plant("business")
org.task("Plan Q3 sprint", dept="operations", priority="high")
org.run(brain=ClaudeBrain())
```

## Querying a trace

```python
task = org.tasks[0]
trace = org.trace_for(task.id)

print(trace.task_id, trace.status, trace.target)
print(f"started: {trace.started_at}, ended: {trace.ended_at}")

for i, entry in enumerate(trace.entries, 1):
    print(f"\n=== think call #{i} (tokens={entry.tokens_used}) ===")
    print(f"system: {entry.system}")
    for msg in entry.messages:
        print(f"  [{msg['role']}] {msg['content'][:100]}")
    print(f"response: {entry.response_content}")
    for tc in entry.response_tool_calls:
        print(f"  → called {tc['name']}({tc['arguments']})")
```

`org.trace_for(id)` reads from mycelium first (so traces persist across process restarts when you use `SqliteBackend` / `FileBackend`), then falls back to the in-memory `TraceObserver`.

## The shape of a Trace

```python
Trace(
    task_id="abc12345",
    node_id="ffd9ea53f9d3",
    target="sales",
    description="Plan Q3 sprint",
    started_at=1717..., ended_at=1717...,
    status="done",                          # "done" | "failed"
    result=None,                            # final response text (also in last entry)
    error=None,                             # exception text if failed
    entries=[
        TraceEntry(
            timestamp=1717...,
            messages=[{"role": "user", "content": "..."},
                      {"role": "assistant", "tool_calls": [...]},
                      {"role": "tool", "tool_call_id": "c1", "content": "result"}],
            system="You are the sales lead...",
            tool_names=["get_open_issues"],
            response_content="Sprint goal: fix the 4 high-sev issues",
            response_tool_calls=[],          # populated when this turn asked for tools
            tokens_used=247,
            finish_reason="stop",
        ),
        TraceEntry(...),                     # one per Brain.think call
    ],
)
```

## Common debugging patterns

### Why did this task fail?

```python
failed = [t for t in org.tasks if t.status == "failed"]
for t in failed:
    trace = org.trace_for(t.id)
    print(f"{t.target}: {trace.error}")
    if trace.entries:
        print(f"  last response before failure: {trace.entries[-1].response_content!r}")
```

### Which agent burned the most tokens?

```python
import collections

by_node = collections.Counter()
for t in org.tasks:
    trace = org.trace_for(t.id)
    if trace is None:
        continue
    by_node[trace.target] += sum(e.tokens_used for e in trace.entries)

for target, tokens in by_node.most_common():
    print(f"  {target}: {tokens}")
```

### Which tools were actually called?

```python
import collections
tool_use = collections.Counter()
for t in org.tasks:
    trace = org.trace_for(t.id)
    if not trace:
        continue
    for entry in trace.entries:
        for tc in entry.response_tool_calls:
            tool_use[tc["name"]] += 1

for tool, count in tool_use.most_common():
    print(f"  {tool}: {count} call(s)")
```

### Stream events live (without aggregation)

```python
from ormica.observe import LogObserver
import sys

org.subscribe(LogObserver(stream=sys.stdout))
org.run(brain=ClaudeBrain())
# 2026-06-05T01:23:45Z run.started src=runner n_tasks=3 mode=sync
# 2026-06-05T01:23:45Z task.started src=runner task_id=abc12345 target=sales ...
# 2026-06-05T01:23:46Z think.recorded src=agent task_id=abc12345 ...
# 2026-06-05T01:23:47Z task.done src=runner task_id=abc12345 tokens_used=247
# 2026-06-05T01:23:47Z run.completed src=runner processed=3 succeeded=3 failed=0
```

## Exporting traces (audit, BI, archival)

`ormica trace --format json` dumps one trace as a JSON document. `ormica export` bulk-exports every stored trace as JSON Lines or CSV — one trace per line in JSONL so the output stays streamable for large colonies.

```bash
# A single trace as portable JSON (full structure).
ormica trace <task_id> --format json > one.json

# Every persisted trace as JSON Lines (default).
ormica export                              > traces.jsonl

# CSV summary — one row per task; great for a quick BI import.
ormica export --format csv                 > summary.csv

# CSV detail — one row per think call, with per-call token cost.
ormica export --format csv --mode detail   > calls.csv

# Or write directly to a file (status reported on stderr).
ormica export --format csv --out traces.csv
```

The same pure functions live in `ormica.observe` for Python use:

| Function | Output |
|---|---|
| `trace_to_dict(trace)` | Plain dict (nested entries preserved) |
| `trace_to_json(trace)` | Pretty-printed JSON string |
| `traces_to_jsonl(iter)` | One compact JSON object per line |
| `traces_to_csv_summary(iter)` | CSV string, one row per task |
| `traces_to_csv_detail(iter)` | CSV string, one row per think call |

CSV cells with newlines in the description or response are collapsed to single spaces so a multi-line value doesn't split the row. Detail-mode responses are truncated at 200 chars with a trailing ellipsis — the JSON forms keep the full text.

## What lives where

| Where | What |
|---|---|
| `org.trace_for(task_id)` | Full Trace with all entries |
| `mycelium.read(f"traces/{task_id}")` | Same data as JSON dict (persisted with `SqliteBackend` / `FileBackend`) |
| `mycelium.read(f"tasks/{task_id}")` | Lightweight task record (status, result, error) — no entries |
| `CollectObserver().events` | Raw `Event` stream (no aggregation) |
| `CounterObserver().counts` | Tallies by event type |

## What's NOT captured

- **The brain's internal reasoning** (Claude's `thinking` blocks, GPT's chain-of-thought) — only the final `response.content` is recorded. Extended thinking is provider-side.
- **Memory writes / signal emits** — those land in `mycelium` and the stigma trail; the Thought Trail is about *think* calls.
- **Soft constitution violations** — they're returned from `enforce()` but not yet emitted as events. Adding a `RuleEvent` is a small follow-up.

## Related

- [Pillar 4 — Observability](../architecture/05-observability.md) — the architecture.
- [Persistence](./persistence.md) — making traces survive restarts.
- [Writing a Constitution](./writing-a-constitution.md) — how rule failures show up in traces.
