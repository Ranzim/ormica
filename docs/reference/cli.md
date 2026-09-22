# CLI reference

The `ormica` command — installed by `pip install -e .`.

```
ormica <subcommand> [flags]
```

## Subcommands

| Command | What it does |
|---|---|
| `ask` | Run one prompt through a fresh colony and print the answer — no config needed. |
| `solve` | Decompose a goal via recursive delegation (honours `--preference`). |
| `doctor` | Check the environment: provider SDKs, API-key presence (never values), sandbox. |
| `version` | Print the installed `ormica` version. |
| `health` | Show a colony's health snapshot (task states, dead-letter, node count). |
| [`init`](#ormica-init) | Create a starter `ormica.yaml`. |
| [`run`](#ormica-run) | Process the config's defined tasks. Sync by default, async with `--async`. |
| [`status`](#ormica-status) | Show the org's tree + defined tasks without running. |
| [`colonies`](#ormica-colonies) | List registered colonies and their descriptions. |
| [`rules`](#ormica-rules) | List the active Constitution — org-level + per-node rules. |
| [`signals`](#ormica-signals) | List stigma trails currently in shared memory, sorted by strength. |
| [`trace`](#ormica-trace) | Dump a stored Thought Trail for a task by id. |

### Quick start (no config file)

```bash
pip install ormica
ormica doctor                                   # what's installed / which keys are set
ormica ask "What is 6 * 7?" --brain gemini      # one prompt, real answer
ormica solve "plan a product launch" --brain claude --preference quality
```

`--preference` is one of `balanced` · `cost` · `quality` · `speed` and biases how
deeply the colony decomposes and how hard it verifies (see
[Preferences](../../ormica/preferences.py)).

---

## `ormica init`

Create a starter `ormica.yaml`.

```
ormica init NAME [--owner OWNER] [--industry NAME-or-path]
                 [--brain {mock,claude,openai}]
                 [--out PATH] [--force]
```

| Flag | Default | Notes |
|---|---|---|
| `NAME` | (required) | Organization name. |
| `--owner` | `""` | Human-in-the-loop. |
| `--industry` | `business` | Colony name (`business`, `supply_chain`, …) **or** path to a colony YAML. |
| `--brain` | `mock` | Default brain type. Picks a matching model: `claude-opus-4-7` / `gpt-4o`. |
| `--out` | `ormica.yaml` | Where to write the config. |
| `--force` | off | Overwrite an existing config. |

Examples:

```bash
ormica init "My SaaS"
ormica init "Globex" --industry supply_chain --brain openai
ormica init "Acme" --industry ./my-saas.yaml --brain claude
```

---

## `ormica run`

Process all pending tasks in the config.

```
ormica run [--config ormica.yaml]
           [--brain {mock,claude,openai}]
           [--async] [--concurrency N]
```

| Flag | Default | Notes |
|---|---|---|
| `--config` | `ormica.yaml` | Path to the config file. |
| `--brain` | (from config) | Override the configured brain type. Also picks the matching default model. |
| `--async` | off | Use the async runner — fans out same-priority tasks concurrently. |
| `--concurrency` | `5` | Max concurrent tasks when `--async` is set. |

Exit codes:

| Code | Meaning |
|---|---|
| `0` | All tasks succeeded. |
| `1` | Config missing / invalid. |
| `2` | At least one task failed. |

Output:

```
processed=4 succeeded=3 failed=1
  [ok]   [high]   sales: Contacted Acme, Globex, Initech.
  [ok]   [normal] finance: Q3 burn forecast clean.
  [ok]   [normal] marketing: 3 campaigns drafted.
  [fail] [low]    ghost: NodeNotFound: no node named 'ghost'
```

Examples:

```bash
ormica run                                # use mock brain from config
ormica run --brain claude                 # override with Claude (default model)
ormica run --async --concurrency 10       # concurrent run with cap
```

---

## `ormica status`

Show what the config defines, without running anything. Useful as a dry-run sanity check.

```
ormica status [--config ormica.yaml]
```

Output:

```
name:     My SaaS
owner:    Ranzim
industry: business
brain:    mock (model=mock)
tree (5 nodes):
  - My SaaS [root]
    - operations [operations]
    - sales [sales]
    - marketing [marketing]
    - finance [finance]
tasks defined: 1
  - [high] sales: Reach out to 3 SMB leads
```

---

## `ormica colonies`

List registered colonies and their descriptions.

```
ormica colonies
```

Output:

```
business: Generic business — operations, sales, marketing, finance.
supply_chain: End-to-end supply chain — procurement, warehouse, logistics, quality.
```

Custom colonies registered via `@register` or `load_colony(..., register=True)` appear here too.

## Related

- [Getting started](../getting-started.md) — the typical workflow.
- [ormica.yaml schema](./ormica-yaml.md) — every config field.
- [Async + Router](../guides/async-and-routing.md) — when to use `--async`.
