# Contributing to Ormica

Thanks for your interest. This guide is short — read it once, then dive into the [docs](./docs/).

## Where to start

1. **Skim the philosophy** — [`docs/concepts.md`](./docs/concepts.md) (three biological metaphors fused into one framework).
2. **Read one architecture doc** that matches what you're touching. See [`docs/architecture/README.md`](./docs/architecture/README.md) for the map.
3. **Run the suite** — `pytest`. 310+ tests, ~400ms. Stays green or your PR isn't ready.

## Development setup

```bash
git clone https://github.com/Ranzim/ormica.git
cd ormica
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                          # confirm 310+ passed
```

Optional provider extras (only needed if you're touching the matching adapter):

```bash
pip install -e ".[claude]"      # anthropic SDK
pip install -e ".[openai]"      # openai SDK
pip install -e ".[memory]"      # chromadb (future vector backend)
pip install -e ".[all]"         # all of the above
```

## Where to put what

| You're adding… | Goes in… | Doc to read first |
|---|---|---|
| A new industry / department layout | `ormica/colony/<name>/` or a YAML file | [Writing a colony](./docs/guides/writing-a-colony.md) |
| A new LLM provider | `ormica/brain/<provider>.py` | [Brain](./docs/architecture/03-brain.md) |
| A new persistence backend | `ormica/mycelium/<name>_backend.py` | [Persistence](./docs/guides/persistence.md) |
| A business rule / safety constraint | A `Rule` in user code, *not* the core | [Writing a Constitution](./docs/guides/writing-a-constitution.md) |
| A general-purpose observability hook | `ormica/observe/<observer>.py` | [Observability](./docs/architecture/05-observability.md) |
| A real-world integration (Gmail, Notion, Stripe…) | `ormica/integrations/<service>/` | (skeleton only — propose a design first) |
| A new CLI subcommand | `ormica/cli/main.py` | [CLI reference](./docs/reference/cli.md) |

## Hard rules of the codebase

1. **Core stays industry-agnostic.** Anything industry-specific belongs in `colony/`, never in `arbor` / `canopy` / `mycelium` / `stigma`.
2. **Brain *generates*, cortex *constrains*.** Don't put policy decisions in the brain layer; don't put LLM logic in the cortex layer.
3. **Failures don't abort a run.** A bad task fails *its* run; the loop keeps going. Same for bad observers.
4. **Naming reflects function.** Module name = what it actually does (see `docs/architecture/README.md` for the metaphor map).
5. **No emojis in code or docs unless explicitly requested.** Keep output portable, grep-friendly.
6. **No new dependencies without justification.** `pyyaml` and `pydantic` are the baseline; LLM/storage extras are optional installs.

## Adding tests

- Use the **`MockBrain`** / **`AsyncMockBrain`** to avoid API costs. They support scripted text replies AND scripted tool calls.
- For persistence, use `tmp_path`. Tests in `test_sqlite_backend.py` and `test_file_backend.py` show the pattern.
- For async, mark with `@pytest.mark.asyncio`. The mode is `strict`.
- For new core modules, **target ~15 tests** covering: happy path, edge cases, integration with one other module.

## Style

- Run `ruff` before submitting (`ruff check .`). The CI is on Python 3.10/3.11/3.12.
- 100-char line length (set in `pyproject.toml`).
- Type hints everywhere on public surfaces. Internal helpers can omit them.
- Comments only when the *why* is non-obvious. Don't restate what the code says.

## Pull requests

1. Fork the repo and create a branch.
2. Make the change. Add tests.
3. Run `pytest` (green) and `ruff check .` (clean).
4. Open a PR with a clear *what* and *why*. Link the issue if there is one.
5. Update any affected docs in `docs/`.

## Where to ask

- **Bug / feature ideas** — GitHub Issues.
- **Design questions** — open a Discussion or draft PR first; the design seam matters more than the code.

Be kind, be clear.
