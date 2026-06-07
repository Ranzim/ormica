# SaaS Helpdesk — production example

A complete customer support colony for a SaaS company. Four departments, real Constitution rules per department, an org-wide Constitution on top, mock tools that map onto real systems (CRM lookup, subscription status, email, escalation), and persistent traces.

**This is the example to read when you want to see Ormica solve a real problem.**

```
┌─────────────────────────────────────────────────────────────────┐
│ Acme SaaS Support                                               │
│ ├── triage           (classify the ticket, route it)            │
│ ├── billing          (subscriptions, refunds — token-capped)    │
│ ├── technical        (API errors — credentials banned)          │
│ └── escalation       (human follow-up; no over-promises)        │
└─────────────────────────────────────────────────────────────────┘
```

## Run it

```bash
cd examples/saas_helpdesk
python run.py
```

You should see a live event ticker as each ticket flows through the colony:

```
» task 6268edc6 started  (target=billing priority=high)
  Ticket #T-1002 (acme-cust-001): Follow-up on the same billing question.
✓ task 6268edc6 done     (tokens=14)
...
result: processed=6 succeeded=6 failed=0
persisted traces: 6
  inspect one with: ormica trace 6268edc6 --config examples/saas_helpdesk/ormica.yaml
```

No API key required — the `mock` brain replays scripted realistic replies so the example is deterministic. To run with a real LLM, see [Switching to a real brain](#switching-to-a-real-brain) below.

## What's in the box

```
examples/saas_helpdesk/
├── README.md       ← you are here
├── ormica.yaml     ← top-level config + org-wide Constitution
├── colony.yaml     ← four departments + per-department rules
├── tools.py        ← mock CRM, billing, email, escalation tools
└── run.py          ← driver script
```

## How governance is layered

**Org-wide Constitution** in `ormica.yaml` — applies everywhere:

| Rule | Why |
|---|---|
| `max_depth: 3` | Bounded growth. No agent can spawn deeper than three levels. |
| `max_tokens: 50000` | Org-wide budget cap; no run can exceed this. |
| `block_role: legal` | Legal calls are human-only; never auto-spawn a legal agent. |
| `banned_words: [internal-only, do not share, confidential-roadmap]` | Org-wide content guard against leaking internal info. |

**Per-department rules** in `colony.yaml` — attached to that department's node, cascade to anything spawned under it:

| Department | Rule | Why |
|---|---|---|
| `triage` | `block_prompt_pattern: no-ticket` | Refuse prompts without a ticket id. |
| `triage` | `max_response_tokens: 500` | Triage replies should be short. |
| `billing` | `banned_words: [stripe-internal, ledger-export, audit-only]` | Don't name internal accounting tools. |
| `billing` | `max_response_tokens: 1500` | Cap per-call cost. |
| `billing` | `min_response_length: 20` | Reject empty/error replies. |
| `technical` | `banned_words: [api_key, password, secret_token, bearer_token]` | Never echo credentials back. |
| `technical` | `max_response_tokens: 2000` | Cap per-call cost. |
| `escalation` | `banned_words: [guaranteed, immediately, refunded today, problem solved]` | No over-promises before a human reviews. |
| `escalation` | `min_response_length: 30` | Force a real acknowledgment, not a one-word reply. |

A hard violation at any layer raises `RuleViolation`; the failing task is marked `failed`; the rest of the run continues. Soft violations would emit a `rule.soft_violation` event onto the bus without blocking.

## What the tools represent

The functions in `tools.py` are minimal mocks. In production you'd swap them for the real API call:

| Tool | Mock returns | Real-world replacement |
|---|---|---|
| `lookup_customer(id)` | One line from a hardcoded dict | Your CRM API call |
| `get_subscription_status(id)` | "Growth (active)" etc. | Stripe / Chargebee API |
| `send_email(to, subject, body)` | "queued email to ..." | Postmark / SES API |
| `escalate_to_human(ticket_id, reason)` | "ticket X escalated" | Your on-call paging system |
| `create_internal_note(ticket_id, note)` | "note added to X" | Your ticketing system API |

The Constitution rules don't change when you swap the implementation — they govern *what the agent says*, not *how the tools work*.

## Inspecting a run

After `python run.py` writes traces into `./helpdesk.db`, you can ask Ormica what happened on any specific ticket:

```bash
ormica trace <task_id> --config examples/saas_helpdesk/ormica.yaml
```

The output is the full Thought Trail for that task: the prompt, the system prompt, the response, tokens used, any tool calls. This is the audit story — every reasoning step persists so you can debug what the colony did and why.

## Switching to a real brain

The example ships with `brain.type: mock` so it runs offline. To swap in a real LLM:

```yaml
# ormica.yaml
brain:
  type: claude            # or openai, gemini, ollama, openrouter, groq, …
  model: claude-opus-4-7  # or another model name
  # Remove the `replies:` block — the real brain will think.
```

Set the relevant env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) and re-run `python run.py`. Every other piece — the colony, the Constitution, the tools, the persistence — works the same.

## What you'd extend in a real deployment

- Plug each tool into the real API behind it.
- Replace the scripted ticket list with a webhook handler that creates `org.task(...)` calls when a ticket arrives.
- Subscribe a `LogObserver(stream=open("audit.log", "a"))` alongside the existing `TraceObserver` for an append-only audit log.
- Swap `memory_db` for a `SqliteBackend` on a shared volume so multiple workers share the colony state.
- Add severity-based rules: a `severity="soft"` rule that emits a metric without blocking, and a `severity="hard"` rule that fails the task.

## See also

- [Writing a Constitution](../../docs/guides/writing-a-constitution.md) — every rule shape used here, explained.
- [Writing tools](../../docs/guides/writing-tools.md) — the `@tool` decorator.
- [Reading the Thought Trail](../../docs/guides/reading-the-thought-trail.md) — what `ormica trace` shows you.
