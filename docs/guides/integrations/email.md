# Email integration — send mail from an Ormica colony

A `send_email(to, subject, body)` tool an agent can call to drop messages into your team's inbox. Uses Python's stdlib `smtplib` so there are no extra dependencies — works with Gmail, SES, Postmark, Mailgun, your own server.

## 1. Decide which SMTP server

Three common choices:

| Provider | Host | Port | Notes |
|---|---|---|---|
| **Gmail** | `smtp.gmail.com` | `587` (STARTTLS) | Use an [App Password](https://myaccount.google.com/apppasswords), not your account password. |
| **SES (AWS)** | `email-smtp.us-east-1.amazonaws.com` | `587` | Use SES SMTP credentials, not your IAM key. |
| **Postmark / Mailgun** | provider-specific | `587` | Their dashboard prints exact config. |

Store the credentials as env vars:

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="ops@example.com"
export SMTP_PASS="..."
export SMTP_FROM="ops@example.com"
```

## 2. The tool

Drop this into your project's `tools.py`:

```python
import os
import smtplib
from email.message import EmailMessage

from ormica.brain import tool


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send a plain-text email."""
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    sender = os.environ.get("SMTP_FROM", user or "")

    if not (host and user and password and sender):
        return "SMTP_* env vars are not set; not sending"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
    except Exception as exc:
        return f"send failed: {type(exc).__name__}: {exc}"

    return f"sent to {to}, subject={subject!r}"
```

The tool returns a human-readable status string so the Thought Trail records what happened — the agent's next think call sees the result as a tool message.

## 3. Wire it into your agent

Same shape as any other tool:

```python
from ormica import Agent, Ormica
from ormica.brain import ClaudeBrain

from tools import send_email

org = Ormica("Acme")
org.plant("business")

agent = Agent(org.find("sales"), ClaudeBrain(), constitution=org.constitution)
agent.act_with_tools(
    "Email the daily lead summary to ops@acme.com.",
    tools=[send_email],
)
```

## 4. Rules to keep this safe

```yaml
constitution:
  rules:
    # Bound damage if an agent decides to mass-email.
    - max_response_tokens: 2000
    - max_tokens: 100000

    # Never put credentials in an outbound email body.
    - banned_words: [api_key, password, secret_token, bearer_token, sk-]
```

Per-department: attach a `max_response_tokens` to the `marketing` template if you want stricter limits on outbound marketing copy than on internal notifications. See [Per-node rule overrides](../writing-a-constitution.md#per-node-rule-overrides).

For human-in-the-loop control over sensitive sends (legal, contracts), wrap the tool with a `CallbackApprover` — see [Human approvals](../human-approvals.md).

## 5. Audit

Every tool call lands in the Thought Trail:

```bash
ormica trace <task_id> | grep send_email
ormica export --format csv --mode detail | grep send_email
```

Use this to confirm:
- Which agent decided to send the message,
- What `to:` / `subject:` / `body:` it provided as arguments,
- What the SMTP server replied (the tool's return string),
- How many tokens the decision cost.

## 6. Production notes

- **HTML email**: replace `msg.set_content(body)` with `msg.add_alternative(html_body, subtype="html")`.
- **Attachments**: `msg.add_attachment(blob, maintype="application", subtype="pdf", filename="report.pdf")`.
- **Rate limits**: most providers cap sends per second. Wrap the tool body with a `time.sleep()` based on a token bucket, or use a job queue (Celery, RQ) and have the tool enqueue rather than send directly.
- **Idempotency**: include a stable `Message-ID` derived from the task id so retried tool calls don't double-send. `msg["Message-ID"] = f"<{task_id}@acme.com>"`.

## Related

- [Writing tools](../writing-tools.md) — the `@tool` decorator and tool loop.
- [Writing a Constitution](../writing-a-constitution.md) — rules that bound what agents can say in outbound mail.
- [Slack integration](./slack.md) — same pattern, different surface.
- [Human approvals](../human-approvals.md) — gate sensitive sends.
