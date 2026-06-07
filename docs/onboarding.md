# Onboarding — your first 5 minutes with Ormica

This is the plain-English tutorial. No metaphors, no architecture diagrams — just *do these things, in this order, and you'll have a working colony.*

If you'd rather read the philosophy first, jump to [`concepts.md`](./concepts.md). If you want to see a real production-style setup, jump to the [SaaS helpdesk example](../examples/saas_helpdesk/README.md). Otherwise, start here.

---

## What is Ormica, in one paragraph

You write a YAML file describing a few "departments" (people-like roles), give them a task each, and Ormica runs an LLM agent for each task. The framework gives you four things you'd otherwise build yourself: a tree of agents that can grow, a shared-memory layer they coordinate through, **rules you can enforce so the agents stay in their lane**, and a full audit trail of every decision they made. Think "agents-as-an-org-chart, with a constitution."

---

## Step 1 — Install (1 minute)

```bash
git clone https://github.com/Ranzim/ormica.git
cd ormica
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Sanity check:

```bash
pytest -q              # should say 4xx passed
ormica --help          # should show subcommands: init, run, status, rules, signals, trace, …
```

If both work, you're done with step 1.

---

## Step 2 — Create a colony (30 seconds)

```bash
ormica init "My SaaS" --industry business
```

This writes `ormica.yaml` in your current directory. Open it. The defaults give you:

- a tree with four departments (operations, sales, marketing, finance)
- a `mock` brain that replies with scripted text (so no API key required yet)
- no tasks yet

---

## Step 3 — Add a task and run it (30 seconds)

Replace your `ormica.yaml` with this:

```yaml
name: My SaaS
industry: business
brain:
  type: mock
  replies:
    - "Booked 3 demos this week — leads forwarded to AE."
tasks:
  - description: "Find 3 SMB leads"
    dept: sales
    priority: high
```

Then:

```bash
ormica run
```

You should see a live event ticker — one line per task — and a final summary saying `processed=1 succeeded=1 failed=0`. That's a working colony.

---

## Step 4 — Swap in a real LLM (1 minute)

The mock brain is great for tests but doesn't think. To run with Claude:

```bash
export ANTHROPIC_API_KEY=sk-...
```

Edit `ormica.yaml`:

```yaml
brain:
  type: claude
  model: claude-opus-4-7
  # Remove the `replies:` block — the brain will now think.
```

Run again:

```bash
ormica run
```

Same thing as before, but now the response comes from a real model. For other providers, set the appropriate env var and pick a provider in `brain.type` — see [`docs/guides/llm-providers.md`](./guides/llm-providers.md) for the full list (Claude, OpenAI, Gemini, Ollama, OpenRouter, Groq, Together, DeepSeek, and any OpenAI-compatible endpoint).

---

## Step 5 — Add a rule (1 minute)

This is the moment Ormica becomes more than "an agent runner."

Add a `constitution:` block to `ormica.yaml`:

```yaml
constitution:
  rules:
    - max_tokens: 10000            # whole org can't spend more than 10k tokens
    - banned_words: [secret, internal-only]  # responses must not contain these
    - block_role: legal            # never auto-spawn a legal agent — humans only
```

Now run again. If the model produces a response containing the word "secret", the task fails — `RuleViolation` — and the rest of the run continues. The model never decided to follow the rule; the rule was enforced *outside* the model. That's the difference between "asking nicely" and "governance."

You can do the same per-department by editing the colony YAML — see [Writing a Constitution](./guides/writing-a-constitution.md) for the full guide.

---

## Step 6 — See what happened (1 minute)

After a run, every think call is captured as a "Thought Trail" persisted to a tiny local SQLite database. To inspect:

```yaml
# ormica.yaml
memory_db: ./my-saas.db
```

```bash
ormica run                          # runs + persists traces
ormica trace <task_id>              # dumps the full reasoning trail for one task
ormica rules                        # what rules are currently in force
ormica signals                      # what pheromone trails exist in shared memory
```

The `task_id` is the 8-character id shown next to each task in the ticker.

---

## You're done with the basics

In about five minutes you've installed Ormica, run a colony, swapped to a real LLM, added a governance rule, and inspected a trace. That's the entire happy path.

### Where to go next

| If you want to… | Read this |
|---|---|
| See a **production-style example** with four departments + real rules | [`examples/saas_helpdesk/README.md`](../examples/saas_helpdesk/README.md) |
| Understand **why** it's built this way | [`concepts.md`](./concepts.md) |
| Write your own **custom colony** (your industry, your roles) | [Writing a colony](./guides/writing-a-colony.md) |
| Build **multiple rules** (per-department, soft vs hard, post-stage) | [Writing a Constitution](./guides/writing-a-constitution.md) |
| Give agents **tools** they can call | [Writing tools](./guides/writing-tools.md) |
| Debug an agent's reasoning | [Reading the Thought Trail](./guides/reading-the-thought-trail.md) |
| Run async / parallel | [Async and routing](./guides/async-and-routing.md) |
| Set up real persistence | [Persistence](./guides/persistence.md) |

### What you skipped

This guide deliberately glossed over:

- **Stigma (pheromone signals)** — agents leaving traces other agents can follow. See [Pillar 2: Signaling](./architecture/02-signaling.md).
- **Canopy (permission chain)** — humans approving high-risk agent spawns. See [Pillar 1: Hierarchy](./architecture/01-hierarchy.md).
- **Per-node rules** — different limits per department, not just org-wide. See the rules guide.
- **Tools** — letting agents call `lookup_customer()` etc. See the tools guide.

These are the things that turn a 5-minute demo into a production system. The order they're introduced above is roughly the order they become important.

### Help

- Found a bug or want to contribute? See [`CONTRIBUTING.md`](../CONTRIBUTING.md).
- Found a security issue? Use [GitHub Private Vulnerability Reporting](https://github.com/Ranzim/ormica/security/advisories/new) or see [`SECURITY.md`](../SECURITY.md).
- Stuck? Open a [GitHub Discussion](https://github.com/Ranzim/ormica/discussions) — questions are welcome.
