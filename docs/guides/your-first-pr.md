# Your First PR

Want to contribute but not sure where to start? This page is the shortest path from "I'd like to help" to "my PR is merged."

## 1. Pick something small (15 minutes)

Browse open issues labeled [`good first issue`](https://github.com/Ranzim/ormica/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) — those are explicitly sized for newcomers and someone has already thought through the design.

If there are none yet, here are five categories of contributions that almost always need help:

| Category | Examples | Doc to read first |
|---|---|---|
| **A new colony** in YAML | `healthcare.yaml`, `ecommerce.yaml`, `law_firm.yaml` | [Writing a colony](./writing-a-colony.md) |
| **A new tool** for an existing colony | `web_search`, `query_db`, `send_email` | [Writing tools](./writing-tools.md) |
| **A docs page improvement** | Better examples, clarified terms, fixed typos | Just the doc itself |
| **A test for an edge case** | "What if X is None?", "What if Y is empty?" | [`tests/`](../../tests/) |
| **A small bug fix** | Anything in [issues labeled `bug`](https://github.com/Ranzim/ormica/labels/bug) | The bug report |

None of those need core-engine changes — the lowest-risk place to start.

## 2. Set up locally (5 minutes)

```bash
git clone https://github.com/Ranzim/ormica.git
cd ormica
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                          # should print "310 passed"
```

If `pytest` is green, your dev environment is good. Move on.

## 3. Find where your change lives

Use this matrix to navigate the codebase. It's the same one in [`CONTRIBUTING.md`](../../CONTRIBUTING.md), repeated here so you don't have to leave this page.

| You're adding / changing… | File(s) | Read first |
|---|---|---|
| A new colony (Python) | `ormica/colony/<name>/__init__.py` + `@register` | [Writing a colony](./writing-a-colony.md) |
| A new colony (YAML) | a `.yaml` file you point `industry:` at | [Writing a colony](./writing-a-colony.md) |
| A new tool | wherever you call `agent.act_with_tools(...)` | [Writing tools](./writing-tools.md) |
| A safety rule / business constraint | A `Rule` in *your own* code (the framework stays domain-agnostic) | [Writing a Constitution](./writing-a-constitution.md) |
| A new LLM provider | `ormica/brain/<provider>.py` + lazy export in `ormica/brain/__init__.py` | [Brain](../architecture/03-brain.md) |
| A new persistence backend | `ormica/mycelium/<name>_backend.py` | [Persistence](./persistence.md) |
| A new observer (metrics, log sink, dashboard hook) | `ormica/observe/<observer>.py` | [Observability](../architecture/05-observability.md) |
| A real-world integration (Gmail, Slack, Stripe, …) | `ormica/integrations/<service>/` | Open an issue to scope first |
| A new CLI subcommand | `ormica/cli/main.py` | [CLI reference](../reference/cli.md) |
| A docs improvement | `docs/` | The page itself |

## 4. Write your change (and a test)

The non-negotiables:

1. **Add a test** in `tests/`. Pattern: copy a similar existing test, change the names. Use `MockBrain` / `AsyncMockBrain` so no API calls happen in CI.
2. **Run `pytest`** — green or your PR isn't ready.
3. **Run `ruff check .`** — clean.
4. **No emojis in code** unless explicitly part of an example.
5. **Comments only when the *why* is non-obvious.** Don't restate what the code says.

A good rule of thumb: **a small PR is a fast PR**. One concept per PR. If you're adding both a new colony *and* a new brain adapter, split them.

## 5. Open the PR

```bash
git checkout -b your-branch-name
# … make changes …
git add <paths>
git commit -m "Short imperative summary of what changed"
git push -u origin your-branch-name
```

Then open a PR on GitHub. The PR template will guide you — it asks for:

- What changed (one sentence)
- Why (the problem this solves)
- Which area / pillar
- The pre-merge checklist

## 6. The review loop

What to expect:

| Step | Who | Typical time |
|---|---|---|
| Automated CI runs | GitHub Actions | < 5 min |
| First review comment | Maintainer | 1–3 days |
| Iteration | You + reviewer | varies |
| Merge | Maintainer | once green + approved |

I (the maintainer) review PRs in batches; be patient if the first response takes a couple of days.

## 7. Common reasons PRs need rework

These come up often enough to call out:

| ❌ Don't | ✅ Do |
|---|---|
| Put industry logic in `arbor` / `canopy` / `mycelium` / `stigma` | Put it in `colony/` or in user code |
| Put LLM logic in `cortex/` | Use `brain/` for LLM, `cortex/` for rules |
| Add a hard dependency to the base install | Make it optional via `pyproject.toml` extras |
| Skip the test because "it's obvious" | Write one; it's the contract for future changes |
| Ship a feature without a docs update | Update `docs/` in the same PR |
| Open a giant cross-module PR | Split into one-concept PRs |
| Use `print()` for debugging | Use the `observe` event bus (or remove before push) |

## 8. After your first PR

Welcome to the colony 🐜.

Once you've shipped one PR, you understand the codebase well enough to take on bigger pieces. The next-level contributions are tracked under [`enhancement`](https://github.com/Ranzim/ormica/labels/enhancement) and [`help wanted`](https://github.com/Ranzim/ormica/labels/help%20wanted).

If there's a piece of the [roadmap](../../README.md#%EF%B8%8F-roadmap) you'd like to own, drop a comment on the relevant issue (or open a new one) and tag the maintainer.

## Stuck?

Open a [Discussion](https://github.com/Ranzim/ormica/discussions). No question is too small. The colony grows through the questions you ask.
