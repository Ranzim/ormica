# Ormica Compute Lab — flagship example

The end-to-end demo that shows what Ormica is *for*: a governed, observable
colony that produces **verified** results, not just plausible ones.

A colony of analyst agents each tackle a computation. The loop is the point:

```
model PROPOSES a Python solution
   → the cortex verify stage GROUNDS it: runs the code in the sandbox,
     checks the output against ground truth
   → wrong? the failure is fed back and the agent retries
   → only a correct, actually-executed answer is accepted
```

Nothing trusts the model's arithmetic — every ✓ was executed in an isolated
sandbox and matched a ground-truth value computed the same way.

## Run

```bash
# offline & deterministic — no API key needed (the sandbox still runs real code)
python examples/compute_lab/lab.py

# with a real LLM — it writes the code itself and must pass the sandbox
export ANTHROPIC_API_KEY=...        # or GEMINI_API_KEY / GOOGLE_API_KEY
python examples/compute_lab/lab.py

# watch it live in the 3D colony graph
python examples/compute_lab/lab.py --dashboard
#   → open http://127.0.0.1:8777/graph
```

## What it demonstrates

| Ormica capability | Where it shows up |
|---|---|
| **Sandboxed execution** | every answer is run in `Sandbox` (timeout, isolated cwd, no host env) |
| **Grounded verification + retry** | the `verify` stage runs the code and checks it against ground truth; wrong answers retry with feedback |
| **Colony structure** | one analyst agent per problem, spawned under the root |
| **Thought Trail** | `org.trace_for(task_id)` captures every reasoning step (the run prints the think-call count) |
| **Live observability** | `--dashboard` streams the whole thing to the 3D graph |
| **Pluggable brain** | real LLM if a key is set, deterministic mock otherwise |

## The honest part

Ormica supplies the *harness* — coordination, sandbox, verification, audit. The
*capability* to write correct code comes from the model. This example proves the
harness works end-to-end: a real (or mock) brain proposes, and the engine only
accepts what it can verify by execution. Swap in a real key to see a live model
iterate against the sandbox until its code is correct.
