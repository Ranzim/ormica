# GitHub integration — file issues and comment from an Ormica colony

Unlike the Slack and email guides (which show you how to write your own tool),
GitHub ships **built in**. Import it and hand the tools to an agent:

```python
from ormica.integrations.data import github

agent.act_with_tools("File an issue about the flaky CI job.", tools=github.all_tools())
```

## 1. Prerequisites

The integration talks to GitHub through the **`gh` CLI** — so there is *no
extra Python dependency* and no token to plumb through env vars. Authentication
is whatever `gh` already has.

```bash
brew install gh        # or see https://cli.github.com
gh auth login
gh auth status         # confirm you're logged in
```

If `gh` is missing or unauthenticated, the tools return a clear `error: …`
string (and the low-level helper raises `GitHubError`) so failures surface
instead of hanging.

## 2. The tools

`github.all_tools()` returns five `@tool`-decorated callables:

| Tool | Signature | Returns |
|---|---|---|
| `create_issue` | `(repo, title, body="")` | `#42 created: <url>` |
| `list_issues` | `(repo, state="open")` | one `#num title (state)` per line |
| `get_issue` | `(repo, number)` | title, state, and body |
| `comment_on_issue` | `(repo, number, body)` | `commented on #num: <url>` |
| `list_pull_requests` | `(repo, state="open")` | one `#num title (state)` per line |

`repo` is always `"owner/name"` (e.g. `"Ranzim/ormica"`).

Pick a subset if you want to limit what an agent can do — e.g. read-only:

```python
tools = [github.list_issues, github.get_issue, github.list_pull_requests]
```

## 3. Give it to the right agent

```python
from ormica import Agent, Ormica
from ormica.brain import ClaudeBrain
from ormica.integrations.data import github

org = Ormica("Acme", memory_db="./acme.db")
org.plant("business")

eng = org.find("engineering")
agent = Agent(eng, ClaudeBrain(), constitution=org.constitution)

response = agent.act_with_tools(
    "Open an issue in Ranzim/ormica titled 'Flaky CI' describing the retry loop.",
    tools=github.all_tools(),
)
print(response.content)
```

## 4. Rules to keep this safe

Because agents can now *write* to GitHub, pair the tools with Constitution
guards:

```yaml
# ormica.yaml — under your colony's constitution: block
constitution:
  rules:
    # Don't leak credentials into an issue body or comment.
    - banned_words: [api_key, password, secret_token, bearer_token, sk-]

    # Cap per-think tokens so an agent can't paste a wall of text into an issue.
    - max_response_tokens: 1500
```

For write access on some departments but read-only on others, hand
`github.all_tools()` to the department that may write and the read-only subset
to the rest — see [Per-node rule overrides](../writing-a-constitution.md#per-node-rule-overrides).

## 5. What you get audit-wise

Every GitHub call runs through the tool loop, so it lands in the Thought Trail:

- The decision to call the tool is a `think.recorded` event with `response.tool_calls`.
- The tool result (`"#42 created: https://…"`) is in the next iteration's history.
- It's persisted under `traces/<task_id>` in mycelium.

```bash
ormica trace <task_id> --format json | jq '.entries[].response_tool_calls'
```

## 6. Going beyond the built-in tools

The transport is the generic `github._gh_api(endpoint, method=…, fields=…)`
helper — the same shape as `gh api`. To add a tool (labels, milestones,
reviews, releases, …), wrap another endpoint:

```python
from ormica.brain import tool
from ormica.integrations.data import github

@tool
def add_label(repo: str, number: int, label: str) -> str:
    """Add a label to an issue or PR."""
    try:
        github._gh_api(
            f"repos/{repo}/issues/{number}/labels",
            method="POST",
            fields={"labels[]": label},
        )
    except github.GitHubError as e:
        return f"error: {e}"
    return f"labeled #{number} with {label!r}"
```

## Related

- [Writing tools](../writing-tools.md) — the `@tool` decorator and tool loop.
- [Writing a Constitution](../writing-a-constitution.md) — `banned_words` and other guards.
- [Slack integration](./slack.md) · [Email integration](./email.md) — same pattern, different surface.
