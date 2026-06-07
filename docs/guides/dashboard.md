# The web dashboard

A stdlib-only web UI for an Ormica colony — tree, signals, rules, stored traces, and a live event stream. No new dependencies, no build chain.

```bash
ormica dashboard --config ormica.yaml
# → ormica dashboard: http://127.0.0.1:8000  (Ctrl+C to stop)
```

Open the URL in any browser. The overview shows colony counts and a live-events ticker; the nav links go to tree, rules, signals, and traces views.

## What you see

| Page | Renders |
|---|---|
| `/` | colony name, node count, rule counts, signal count, trace count, and a real-time event ticker driven by Server-Sent Events |
| `/tree` | every node with its role, current state, and a "(N rule(s))" badge if rules are attached |
| `/rules` | the active Constitution — org-wide rules and per-node rules, each with stage / severity / name / description |
| `/signals` | stigma trails sorted by strength, with source ids |
| `/traces` | every persisted Thought Trail, linked to its detail page |
| `/traces/<task_id>` | a single trace: per-think-call message history, system prompt, tool names, response, token cost |
| `/events` | Server-Sent Events stream — the source for the live ticker on the overview |
| `/healthz` | a tiny `200 ok` endpoint for liveness checks |

## Watch the colony think live

The dashboard subscribes an `SSEObserver` to your `org.events` bus. Anything emitted there is fanned out to every connected browser as one Server-Sent Events frame per occurrence — task start / done / failed, soft rule violations, run start / complete, every `think.recorded`. The overview page hooks `EventSource("/events")` and prepends each event to the live panel in real time.

Run the dashboard in one terminal and `ormica run --config ormica.yaml` in another to watch a run unfold step-by-step in your browser.

## Security

**There is no authentication.** The default bind is `127.0.0.1` only — fine for local development. Don't put this on the public internet without a reverse proxy and auth in front of it.

```bash
# Local only (default, safe)
ormica dashboard

# LAN-exposed (no auth — be careful)
ormica dashboard --host 0.0.0.0
```

The dashboard is **view-only** — no buttons mutate state, no forms POST. The threat surface is read-only data exfiltration plus the SSE event stream.

## Embedding it in your own runtime

If you want to mount the dashboard alongside your own runner (e.g. inside a long-lived service), call `serve()` directly:

```python
from ormica import Ormica
from ormica.dashboard import serve

org = Ormica("Acme", memory_db="./state.db")
# build tree, attach observers, schedule tasks, etc.
serve(org, host="127.0.0.1", port=8000)
```

`serve()` blocks (`KeyboardInterrupt` stops it). Run it in a daemon thread or a separate process if you don't want it to take over the foreground.

## What's missing (and why)

- **No tree visualization** beyond indented text. A real graph view is on the v0.5 list — for now, the ASCII-ish hierarchy on `/tree` is enough to verify your colony has the shape you expected.
- **No filtering on the event stream.** Every event reaches every connected browser. For a colony with thousands of events per minute you'd want server-side filtering — out of scope here, easy follow-up.
- **No persistence of historical events.** SSE shows you what happens while you're connected. For audit history, use `TraceObserver(store=org.memory)` and browse `/traces/<id>` after the fact.

## Related

- [Onboarding](../onboarding.md) — the 5-minute path to a running colony.
- [SaaS helpdesk example](../../examples/saas_helpdesk/README.md) — start the dashboard after running it to inspect the persisted traces visually.
- [Reading the Thought Trail](./reading-the-thought-trail.md) — what each piece of a trace means.
