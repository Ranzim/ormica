# Slack integration — send messages from an Ormica colony

Give an agent a `send_slack_message(channel, text)` tool and a few Constitution rules to keep it from saying anything dangerous in your workspace.

This guide uses **incoming webhooks** — the simplest path: a URL you POST JSON to. No OAuth dance, no Slack app to install on every workspace. For richer flows (replies, threads, interactive buttons) the same pattern extends to the full Slack Web API.

## 1. Get a webhook URL

In Slack:
1. **Apps → Manage → Custom Integrations → Incoming Webhooks** (or create a Slack app and add an Incoming Webhook from the app's settings).
2. Pick the channel the webhook will post to.
3. Copy the URL — looks like `https://hooks.slack.com/services/T.../B.../...`.
4. Store it in an env var:

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

## 2. The tool

Add this to your project's `tools.py` (no extra deps — uses stdlib `urllib`):

```python
import json
import os
import urllib.request

from ormica.brain import tool


@tool
def send_slack_message(channel: str, text: str) -> str:
    """Post a message to Slack.

    ``channel`` is informational here (the webhook URL pins the channel);
    captured in the response so the Thought Trail records intent.
    """
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        return "SLACK_WEBHOOK_URL is not set; not sending"

    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            ok = resp.status == 200
    except Exception as exc:
        return f"send failed: {type(exc).__name__}: {exc}"

    return f"posted to {channel} (ok={ok})"
```

## 3. Give it to the right agent

```python
from ormica import Agent, Ormica
from ormica.brain import ClaudeBrain

from tools import send_slack_message

org = Ormica("Acme", memory_db="./acme.db")
org.plant("business")

# The 'ops' department gets the Slack tool.
ops = org.find("operations")
agent = Agent(ops, ClaudeBrain(), constitution=org.constitution)

response = agent.act_with_tools(
    "Post a heads-up to #ops-alerts that the daily report is queued.",
    tools=[send_slack_message],
)
print(response.content)
```

Or wire it via `act_with_tools` in your runner if you're using `org.run()`. See [Writing tools](../writing-tools.md) for the tool-loop pattern.

## 4. Rules to keep this safe

```yaml
# ormica.yaml — under your colony's constitution: block
constitution:
  rules:
    # Never echo credentials into a chat message.
    - banned_words: [api_key, password, secret_token, bearer_token, sk-]

    # Cap per-think token use so a runaway agent can't post a wall of text.
    - max_response_tokens: 1500

    # Cap org-wide spend so a Slack-tools loop can't burn through your budget.
    - max_tokens: 50000
```

For per-department rules (e.g. operations may post but billing may not), attach them on the relevant template in your colony YAML — see [Per-node rule overrides](../writing-a-constitution.md#per-node-rule-overrides).

## 5. What you get audit-wise

Every `send_slack_message` call goes through the tool loop, so:

- The decision to call the tool is recorded as a `think.recorded` event with `response.tool_calls = […]`.
- The tool result (`"posted to #ops-alerts (ok=True)"`) lands in the next iteration's message history.
- The whole thing is persisted under `traces/<task_id>` in mycelium.

After the run:

```bash
ormica trace <task_id> --format json | jq '.entries[].response_tool_calls'
# → shows every Slack tool call the agent made.

ormica export --format csv --mode detail > calls.csv
# → one row per think call, including which tools fired.
```

## 6. Going beyond webhooks

Same `@tool` pattern, swap the body of the function:

| Want to… | Replace urlopen with |
|---|---|
| Post via Slack Web API (with replies, threads, reactions) | `POST https://slack.com/api/chat.postMessage` with `Authorization: Bearer xoxb-…` |
| Wait for a human approval before continuing | Combine with `CallbackApprover` — see [Human approvals](../human-approvals.md) |
| Run via Slack's Block Kit | Send `{"blocks": [...]}` instead of `{"text": ...}` |

The Thought Trail layer doesn't care which surface you call — every tool result is captured the same way.

## Related

- [Writing tools](../writing-tools.md) — the `@tool` decorator and tool loop.
- [Writing a Constitution](../writing-a-constitution.md) — `banned_words` and other guards.
- [Human approvals](../human-approvals.md) — pair Slack notifications with `CallbackApprover` to gate spawns.
- [Email integration](./email.md) — same pattern, different channel.
