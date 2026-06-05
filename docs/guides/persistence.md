# Persistence

Pick a backend so memory, signals, task records, and traces survive process restarts.

## The three backends

| Backend | File | Writes | Reads | When to use |
|---|---|---|---|---|
| `InMemoryBackend` | (none — RAM) | O(1) | O(1) | Tests, prototypes. Loses everything at exit. |
| `FileBackend` | one `.json` file | O(n) (rewrites whole file) | O(1) | Tiny demos. Human-readable on disk. |
| `SqliteBackend` | one `.db` file | O(1) | O(1) | **The default for anything serious.** WAL mode, concurrent-read safe. |

All three implement the same `Backend` protocol, so swapping is one line.

## Choosing one

### In Python

```python
from ormica import Ormica
from ormica.mycelium import Mycelium, SqliteBackend

# Recommended default
org = Ormica("Acme", memory_db="./acme.db")

# Equivalent long-form
mem = Mycelium(backend=SqliteBackend("./acme.db"))
org = Ormica("Acme", memory=mem)

# Human-readable JSON file (for demos)
org = Ormica("Acme", memory_path="./acme.json")
```

When both `memory_db=` and `memory_path=` are set, **`memory_db` wins**.

### In `ormica.yaml`

```yaml
name: Acme
memory_db: ./acme.db          # → SqliteBackend
# memory_file: ./acme.json     # → FileBackend (alternative)
brain:
  type: claude
```

The CLI's `_build_org` reads these and constructs the backend.

## What's persisted

When you swap a backend in, *everything* that goes through `Mycelium` is automatically persisted:

| Key prefix | Content | Written by |
|---|---|---|
| (free keys) | Arbitrary `org.write(key, value)` calls | Agents, you |
| `stigma/*` | Pheromone signals | Stigma layer |
| `tasks/*` | One record per executed task | Runners |
| `traces/*` | Full Thought Trail per task | `TraceObserver(store=mem)` |

Restart the process, build a fresh `Ormica(memory_db="./acme.db")`, and all of it is there — task history, signal trails, governance audit trail.

## Why prefer SqliteBackend

- **O(1) writes.** `FileBackend` rewrites the entire JSON file on every `set` — fine for 50 entries, not fine for 50k.
- **Concurrent reads.** WAL journal mode means a reader doesn't block on a writer. Important if you're running observability dashboards against live data.
- **Async-runner safe.** Constructed with `check_same_thread=False`, so an `AsyncTaskRunner` can write from any task.
- **No external dependency.** SQLite is stdlib in Python.

`FileBackend` exists for two cases:
1. **Tiny demos** where seeing the JSON on disk helps reason about state.
2. **Hand-edited fixtures** for tests.

## Atomicity

| Backend | Crash safety |
|---|---|
| `FileBackend` | Atomic via write-to-`.tmp` + `os.replace`. Mid-flush crash = old file intact. |
| `SqliteBackend` | SQLite handles it (WAL + `BEGIN; COMMIT` per write). |

Neither does inter-process locking. Single-process recommended; multi-process needs file locking on top.

## Migration

There's no built-in migration between backends, but the data shapes are the same. A quick recipe:

```python
from ormica.mycelium import FileBackend, SqliteBackend

src = FileBackend("./acme.json")
dst = SqliteBackend("./acme.db")
for entry in src.items():
    dst.set(entry)
```

## What's deliberately *not* in this layer

- **Concurrent multi-process writes.** Add file locking (`fcntl` on POSIX) in a new backend when needed.
- **Schema migration.** Both file formats carry `__schema_version: 1`; we'll add a migration hook when the format changes.
- **Remote / network backends.** Postgres, S3, ChromaDB. Each is a new `Backend` impl. `chromadb>=0.5` is already declared as an optional extra in `pyproject.toml`.
- **Encryption at rest.** Add a wrapping backend that encrypts/decrypts in `set`/`get`.

## Related

- [Pillar 2 — Signaling](../architecture/02-signaling.md) — what mycelium does.
- [Reading the Thought Trail](./reading-the-thought-trail.md) — persistence makes traces queryable across runs.
