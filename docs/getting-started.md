# Getting started

Get a working Ormica colony in 5 minutes.

## 1. Install

```bash
git clone https://github.com/Ranzim/ormica.git
cd ormica
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                            # should report 310 passed
```

Optional provider extras:

```bash
pip install -e ".[claude]"        # anthropic SDK
pip install -e ".[openai]"        # openai SDK
pip install -e ".[all]"           # both + chromadb
```

## 2. Hello, Colony (CLI flow)

```bash
ormica init "My SaaS" --industry business
```

This writes a starter `ormica.yaml`:

```yaml
name: My SaaS
owner: ''
industry: business
max_depth: 8
memory_file: ''
memory_db: ''
brain:
  type: mock
  model: mock
  replies:
    - ok
tasks: []
```

Add a task and run it:

```bash
cat > ormica.yaml <<'EOF'
name: My SaaS
industry: business
brain:
  type: mock
  replies: ["3 SMB leads booked for demos"]
tasks:
  - description: "Find 3 SMB leads"
    dept: sales
    priority: high
EOF

ormica run
# → processed=1 succeeded=1 failed=0
#   [ok] [high] sales: 3 SMB leads booked for demos
```

Swap in a real LLM:

```bash
export ANTHROPIC_API_KEY=...
ormica run --brain claude            # or --brain openai with OPENAI_API_KEY
```

Or run **concurrently**:

```bash
ormica run --async --concurrency 5
```

## 3. Hello, Colony (Python flow)

```python
from ormica import Ormica
from ormica.brain import ClaudeBrain

org = Ormica("My SaaS", owner="Founder")
org.plant("business")            # spawns operations / sales / marketing / finance

org.task("Follow up with 3 leads", dept="sales", priority="high")
org.task("Forecast Q3 cash flow", dept="finance")

org.run(brain=ClaudeBrain())
```

That's the full pitch in five lines. The colony self-organizes; you stay at the root.

## 4. The four pillars — at a glance

```
                    YOU (root owner)
                          │
            ┌─────────────┼─────────────┐
            │             │             │
       Operations      Sales      Marketing  …   (arbor: hierarchy)
                          │
                    ┌─────┴─────┐
                    │           │
                  scout       hunter             (each spawn permission-checked: canopy)

All read/write through mycelium (shared memory).
All emit/sense via stigma (pheromone signals).
All thinking goes through brain (LLM seam).
All actions checked against cortex (Constitution).
Every think call captured by observe (Thought Trail).
```

## Next steps

- **Concepts** — [The three biological metaphors](./concepts.md).
- **Architecture** — [Pillars 1–4 in depth](./architecture/README.md).
- **A real custom colony** — [Writing a colony](./guides/writing-a-colony.md).
- **Govern an agent's behavior** — [Writing a Constitution](./guides/writing-a-constitution.md).
- **Debug an agent** — [Reading the Thought Trail](./guides/reading-the-thought-trail.md).
