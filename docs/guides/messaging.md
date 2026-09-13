# Messaging — direct agent-to-agent handoffs

Stigmergy ([signals](../architecture/02-signaling.md)) is *indirect*
coordination: an agent drops a pheromone and whoever cares senses it. But hard
tasks also need *direct* handoffs — "Agent A, I need this specific result before
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

## Pairs well with

- [Planning](./planning.md) — a planner assigns subtasks; agents message to hand off intermediate results.
- [Verification](./verification.md) — ask a peer (or a judge agent) to check work, then reply with the verdict.

> Scope note: this is the messaging *substrate* plus agent/facade helpers.
> Exposing a `send_message` **tool** so an LLM agent can message peers
> autonomously (like the `emit_signal` tool for stigma) is the natural next step.
