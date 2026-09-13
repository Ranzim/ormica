# Verification — make agents produce *checkable* output

The `post` stage of a Constitution is terminal: a hard rule fails, the turn
raises, done. That's right for constraints ("never leak a secret"). But for
*correctness* on hard tasks you usually want a different behaviour: **check the
answer, and if it's wrong, tell the agent why and let it try again.**

That's the `verify` stage. It's what turns a plausible-looking response into a
*validated* one — "the output must be valid JSON", "the code must compile", "the
claim must cite a source", "the sandbox run must pass".

## How it works

`agent.act()` runs a loop: think → check verify rules → if a hard verify rule
fails, re-prompt the brain with the failure reason and try again, up to
`max_verify_attempts` (default 3). If every attempt fails it raises
`VerificationFailed`; if there are no verify rules, behaviour is unchanged
(one think call).

```
think ──► post rules (terminal) ──► verify rules
                                       │ pass ──► return
                                       │ fail ──► feedback + retry (≤ N)
                                       └ exhausted ──► raise VerificationFailed
```

## Built-in verify rules

```python
from ormica import Agent
from ormica.cortex import Constitution, must_be_json, must_contain, must_match, verifier

con = Constitution([
    must_be_json(),                 # response must parse as JSON
    must_contain("summary"),        # substring (case-insensitive)
    must_match(r"\bCVE-\d{4}-\d+"),  # regex (re.search)
])

agent = Agent(node, brain, constitution=con)
response = agent.act("Return a JSON report with a summary.", max_verify_attempts=3)
```

## Custom checks — the real power

`verifier(name, check, ...)` takes any predicate over the context dict. The
context is the `post` context plus `attempt` (1-based). This is where domain
verification lives — compile, run, simulate, or use an LLM as a judge:

```python
from ormica.cortex import verifier

def code_compiles(ctx) -> bool:
    code = ctx["response"].content
    # ...write to a sandbox, run the compiler, return True on exit 0...
    return _sandbox_compile(code)

compiles = verifier(
    "code_compiles",
    code_compiles,
    description="the generated code must compile without errors",
)
```

An **LLM-as-judge** is just a predicate that calls a brain:

```python
judge_brain = ClaudeBrain()

def grounded_in_sources(ctx) -> bool:
    answer = ctx["response"].content
    verdict = judge_brain.think(
        f"Does this answer cite a real source? Reply YES or NO.\n\n{answer}"
    )
    return verdict.content.strip().upper().startswith("YES")

grounded = verifier("grounded", grounded_in_sources,
                    description="the answer must cite a source")
```

The `description` matters: it's fed back to the model on retry, so make it a
clear instruction for how to fix the answer.

## Hard vs soft

- `severity="hard"` (default) — failure triggers retry, then `VerificationFailed`.
- `severity="soft"` — failure emits a `verify` soft-violation event and the
  response is accepted anyway (no retry). Use it to *measure* quality without
  blocking.

## Observability

Every retry emits a `verify.retry` event, and a final give-up emits
`verify.failed` — both carry the rule names and reasons, and land in the
Thought Trail alongside the think calls. So you can always answer *"how many
tries did this take, and what kept failing?"*

## Attaching verify rules per node

Like every rule, verify rules can be attached to a `Node` (`node.rules`) so
they apply to that subtree only — see
[Writing a Constitution](./writing-a-constitution.md#per-node-rule-overrides).

## Related

- [Writing a Constitution](./writing-a-constitution.md) — the Rule model and stages.
- [Reading the Thought Trail](./reading-the-thought-trail.md) — auditing retries.
