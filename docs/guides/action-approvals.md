# Human-in-the-loop action gates

Canopy already puts a human in the loop for **spawns** (the AUTO/CHAIN/ROOT
approval chain — see [Human approvals](./human-approvals.md)). This guide covers
the other half: putting a human in the loop for **actions** — the high-risk tool
calls an agent makes (issue a refund, send an email, run a command, open a PR).

Wrap the tool; a human approves the specific call before it runs.

## The gate

```python
from ormica.approval import require_approval, ConsoleActionApprover

safe_refund = require_approval(issue_refund, ConsoleActionApprover())
agent.act_with_tools("Refund order 123", tools=[safe_refund])
# prompt: approve action issue_refund(order_id='123', amount=4999)? [y/N]:
```

- **Fail-closed:** a denial — or an approver that raises — returns a refusal
  string the model reads, and the underlying tool **never runs**.
- The wrapped tool keeps the original name and schema, so the model calls it
  exactly as before; only its description gains a "requires human approval" note.

## Gate only the risky calls

Interrupting a human for every call is noise. Pass `when` to gate a call only
when its arguments cross a threshold:

```python
safe_refund = require_approval(
    issue_refund,
    ConsoleActionApprover(),
    when=lambda args: args.get("amount", 0) > 1000,   # only large refunds
)
```

Small refunds run straight through; only refunds over $1000 pause for a human.

## Approvers

Mirroring canopy's spawn approvers:

| Approver | Behaviour |
|---|---|
| `AutoApproveActions` | always approves (turn a gate off) |
| `DenyActions` | always denies (lockdown) |
| `ConsoleActionApprover` | interactive y/N in the terminal |
| `CallbackActionApprover` | delegate to your own callable — Slack, a web UI, a queue |

`CallbackActionApprover` is the production seam:

```python
from ormica.approval import CallbackActionApprover

def slack_gate(request):
    ts = post_slack(f"Approve {request.summary()}?")
    return wait_for_button(ts)   # blocks until a human clicks

gated = require_approval(open_pull_request, CallbackActionApprover(slack_gate))
```

The callable receives an `ActionRequest` (`tool_name`, `arguments`, `task_id`)
and returns `bool`.

## Gating several tools at once

```python
from ormica.approval import gate_tools, ConsoleActionApprover

risky = gate_tools([issue_refund, send_email, delete_account], ConsoleActionApprover())
agent.act_with_tools(prompt, tools=[*safe_tools, *risky])
```

## Pairs well with

- [Sandboxed execution](./sandboxed-execution.md) — gate `run_command` behind approval *and* run it in the sandbox.
- [Human approvals](./human-approvals.md) — the spawn-side counterpart; use both to gate *who exists* and *what they do*.
- [Verification](./verification.md) — auto-checks for correctness; approvals for authority. Different jobs, often used together.

## Scope note

The gate wraps a tool's function, so refusals land in the tool loop (and thus
the Thought Trail) as tool results. Emitting a distinct `action.requested` /
`action.denied` event onto the bus is a small follow-up.
