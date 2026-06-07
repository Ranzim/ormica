# `ormica.yaml` schema

Every field, what it does, and the default.

## Full example

```yaml
name: My SaaS                       # required
owner: Ranzim
industry: business                  # colony name OR path to a YAML colony file
max_depth: 8
memory_file: ./mem.json             # FileBackend path (omit if not used)
memory_db: ./mem.db                 # SqliteBackend path (wins over memory_file)
brain:
  type: claude                      # mock | claude | openai
  model: claude-opus-4-7
  replies:                          # only used when type=mock
    - "ok"
tasks:
  - description: "Reach out to 3 SMB leads"
    dept: sales                     # alias for `target`
    priority: high                  # high | normal | low
  - description: "Forecast Q3"
    target: finance
```

## Top-level fields

| Field | Type | Default | What it does |
|---|---|---|---|
| `name` | str | `"My Company"` | Root node name. |
| `owner` | str | `""` | Human-in-the-loop. Appears in tree.owner. |
| `industry` | str | `""` | Colony to plant. Either a registered name (`business`, `supply_chain`) or a path to a colony YAML (`./my-saas.yaml`). Path detection: ends in `.yaml` / `.yml` or contains a `/`. |
| `max_depth` | int | `8` | Arbor depth limit. Spawning past this raises `MaxDepthExceeded`. |
| `memory_file` | str | `""` | If set (and `memory_db` is empty), backs Mycelium with a `FileBackend` at this path. |
| `memory_db` | str | `""` | If set, backs Mycelium with a `SqliteBackend` at this path. Wins over `memory_file`. |

## `brain` section

| Field | Type | Default | What it does |
|---|---|---|---|
| `brain.type` | str | `"mock"` | `mock` · `claude` · `openai` |
| `brain.model` | str | `"claude-opus-4-7"` | Model ID for the chosen provider. For `mock`, ignored. |
| `brain.replies` | list[str] | `["ok"]` | Cycled responses for `MockBrain`. Each can be a string (text response). |

When `brain.type=mock`, the configured `model` is informational. When `type=claude` / `openai`, the model is forwarded to the SDK; the API key comes from `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` env vars.

If you pass `--brain` on the CLI, it overrides `brain.type` *and* picks the matching default model (so `--brain openai` on a Claude config still picks `gpt-4o`, not `claude-opus-4-7`).

## `tasks` section

A list of task definitions, each with these fields:

| Field | Type | Default | What it does |
|---|---|---|---|
| `description` | str | (required) | The task description (becomes the user prompt). |
| `target` | str | `""` | Node name to route to. Empty = root. |
| `dept` | str | `""` | Alias for `target` — easier to read for org-chart colonies. |
| `priority` | str | `"normal"` | `high` · `normal` · `low`. |

If both `target` and `dept` are set on the same task, `dept` wins (see
`ormica/cli/main.py`: the CLI promotes yaml tasks with `dept=t.dept or t.target`).
Pick one or the other for a given task — setting both is a code smell.

## What's *not* in the YAML

- **Constitution** — defined in Python (`Constitution`/`Rule` objects). A YAML loader for rules is a future addition; for now, write them in Python and pass them when building the org programmatically (the CLI doesn't support them yet).
- **Per-node brain (Router)** — same reason. A future `brain.routes` section could express this.
- **Observability subscriptions** — CLI runs use default-no-observers. Subscribe `TraceObserver` / `LogObserver` etc. in Python when needed.

## Loading and saving programmatically

```python
from pathlib import Path
from ormica.cli.config import OrmicaConfig, BrainConfig, TaskConfig, load_config, save_config

config = OrmicaConfig(
    name="Acme",
    industry="business",
    brain=BrainConfig(type="claude", model="claude-opus-4-7"),
    tasks=[TaskConfig(description="say hi", dept="sales", priority="high")],
)
save_config(config, Path("ormica.yaml"))

reloaded = load_config(Path("ormica.yaml"))
```

The dataclasses live in [`ormica/cli/config.py`](../../ormica/cli/config.py).

## Validation

Currently soft — missing fields default; unknown fields are ignored. A stricter `pydantic`-based loader is a possible follow-up.

## Related

- [CLI commands](./cli.md) — how the config is used.
- [Writing a colony](../guides/writing-a-colony.md) — defining a YAML colony to plug into `industry:`.
- [Persistence](../guides/persistence.md) — when to pick `memory_db` vs `memory_file`.
