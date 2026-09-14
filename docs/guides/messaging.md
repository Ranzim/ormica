# Messaging — direct agent-to-agent handoffs

> **Opt-in — not Ormica's default coordination model.** Ormica coordinates
> through **stigmergy**: agents post to a shared pheromone field and coordination
> *emerges*, rather than through direct message-passing (see the
> [philosophy](../../README.md)). The postbox is the deliberate *alternative* for
> the narrow cases where emergence isn't enough and you need a specific, addressed
> handoff. **Prefer [signals](./reading-the-thought-trail.md) + shared memory
> first**; use the postbox only when a direct request is genuinely required. It is
> off unless you wire it in.

Stigmergy ([signals](../architecture/02-signaling.md)) is *indirect*
coordination: an agent drops a pheromone and whoever cares senses it. But some
hard tasks need a *direct* handoff — "Agent A, I need this specific result before
I can continue." The **postbox** provides that: addressed messages, replies, and
threads.

Like `stigma`, it's a thin layer over the shared `Mycelium` (messages live under
the `mailbox/` key prefix), so it persists and uses the same backend as
everything else.

## From an agent

Agents that share a mycelium get shortcuts. `to` is another `Node` (or a node
id):

```python
# alice needs something from bob
alice.send(bob_node, "Send me the pricing table", subject="pricing")

# bob checks his inbox and replies
for msg in bob.fetch_messages():        # returns unread + marks them read
    bob.reply(msg, "Here it is: Growth $499, Scale $2499")

# alice reads the answer
answer = alice.inbox()[0].body
```

Agent methods: `send`, `reply`, `inbox(unread_only=False)`, `unread()`,
`fetch_messages()`. All are no-ops when the agent has no mycelium (same as
`remember`/`emit`).

## From the org facade

The facade resolves department **names** to nodes for you:

```python
org.send("engineering", "sales", "What's the launch date?", subject="launch")

for msg in org.inbox("sales"):
    print(msg.sender, msg.body)
```

## Replies and threads

`reply()` swaps sender/recipient, prefixes the subject with `Re:`, and links
`in_reply_to`. `thread()` reconstructs a full back-and-forth **across both
mailboxes**, oldest first:

```python
box = org.postbox
q = box.send(a.id, b.id, "q1")
a1 = box.reply(q, "a1")
box.reply(a1, "q2")

[m.body for m in box.thread(q)]     # -> ["q1", "a1", "q2"]
```

## The `Message`

```python
Message(sender, recipient, body, subject="", id, in_reply_to=None,
        created_at, read=False, meta={})
```

`sender`/`recipient` are node ids. `read` flips to `True` via `mark_read()` or
`fetch()`. `meta` is free-form for your own annotations.

## Observability

Sending through `agent.send` emits a `message.sent` event (sender, recipient,
subject, message id) into the Thought Trail, so a conversation is auditable
alongside everything else.

## When to use which

| Need | Use |
|---|---|
| "Broadcast that pricing is trending" (whoever cares) | [signals](./reading-the-thought-trail.md) / `stigma` |
| "I specifically need X from you before I continue" | **postbox** (this) |
| "Everyone can read the shared findings" | [mycelium memory](./semantic-memory.md) |

## Letting the LLM message peers autonomously — the `send_message` tool

The methods above are for *your* code. To let the **agent itself** decide to
message a peer mid-turn, give it the `send_message` tool — the direct-messaging
counterpart to stigma's `emit_signal`. It carries the same guardrails: a
**bounded recipient list** (declared as a schema enum, so the model can't invent
recipients), a **per-turn rate limit**, and **refusals returned as strings**
(never raised) so the model can adjust.

Declare it on a node via `meta["message_tool_config"]`; the runner wires it into
that node's tool loop automatically (alongside `emit_signal` if present):

```python
from ormica.postbox import MessageToolConfig

org.find("engineering").meta["message_tool_config"] = MessageToolConfig(
    recipients=("sales", "support"),   # department names, resolved to node ids
    max_per_turn=3,
    max_body_chars=2000,
)
org.task("Coordinate the launch with the other teams", target="engineering")
org.run(brain=brain)   # the agent may now call send_message("sales", "...")
```

### In colony YAML

Declare it on a template — compact (recipients only) or full mapping, mirroring
`emit_tool`:

```yaml
templates:
  - name: engineering
    message_tool: [sales, support]        # compact

  - name: sales
    message_tool:                          # explicit
      recipients: [engineering, support]
      max_per_turn: 3
      max_body_chars: 2000
```

Or build it by hand for a direct `act_with_tools` call:

```python
from ormica.postbox import MessageToolBuilder, MessageToolConfig

tool = MessageToolBuilder(
    org.postbox, node,
    MessageToolConfig(recipients=("sales",)),
    resolve=lambda name: org.find(name).id,
).as_tool()

agent.act_with_tools("Ask sales for the pricing table", tools=[tool])
```

Each `send_message` call lands in `TraceEntry.response_tool_calls`, so what the
agent chose to send is captured in the Thought Trail with no extra wiring.

## Pairs well with

- [Planning](./planning.md) — a planner assigns subtasks; agents message to hand off intermediate results.
- [Verification](./verification.md) — ask a peer (or a judge agent) to check work, then reply with the verdict.
