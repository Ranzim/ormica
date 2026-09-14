"""GitHub integration — issue & pull-request tools agents can call.

Transport is the `gh` CLI (https://cli.github.com), so there is **no extra
Python dependency** and authentication is whatever ``gh auth login`` already
set up. Verify your setup with ``gh auth status``.

Each function is an ormica :class:`~ormica.brain.Tool`. Hand them to an agent
with ``all_tools()``::

    from ormica.integrations.data import github

    agent.act_with_tools(
        "Open an issue about the flaky CI job.",
        tools=github.all_tools(),
    )

Every tool returns a short, LLM-friendly string. Per-call failures (repo not
found, bad number, …) come back as an ``"error: ..."`` string so the tool
loop can recover instead of crashing. Setup problems (gh missing / not
authenticated) raise :class:`GitHubError` so you notice them.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any, Optional

from ormica.brain import tool


class GitHubError(RuntimeError):
    """Raised for setup problems: ``gh`` not installed or not authenticated."""


def _require_gh() -> str:
    """Return the path to the ``gh`` binary or raise :class:`GitHubError`."""
    path = shutil.which("gh")
    if path is None:
        raise GitHubError(
            "the GitHub CLI ('gh') is not installed. Install it from "
            "https://cli.github.com and run `gh auth login`."
        )
    return path


def _gh_api(
    endpoint: str,
    *,
    method: str = "GET",
    fields: Optional[dict[str, Any]] = None,
) -> Any:
    """Call ``gh api`` and return parsed JSON (or ``None`` for empty output).

    Args are passed as a list — never through a shell — so values containing
    spaces or special characters are safe. Raises :class:`GitHubError` when
    ``gh`` is missing, unauthenticated, or the API call fails.
    """
    gh = _require_gh()
    args = [gh, "api", "-X", method, endpoint]
    for key, value in (fields or {}).items():
        args += ["-f", f"{key}={value}"]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "auth" in stderr.lower():
            raise GitHubError(f"GitHub CLI is not authenticated: {stderr}")
        raise GitHubError(stderr or f"`gh api {endpoint}` failed")
    out = proc.stdout.strip()
    return json.loads(out) if out else None


@tool
def create_issue(repo: str, title: str, body: str = "") -> str:
    """Create a GitHub issue. ``repo`` is 'owner/name'. Returns the issue URL."""
    try:
        data = _gh_api(
            f"repos/{repo}/issues",
            method="POST",
            fields={"title": title, "body": body},
        )
    except GitHubError as e:
        return f"error: {e}"
    return f"#{data['number']} created: {data['html_url']}"


@tool
def list_issues(repo: str, state: str = "open") -> str:
    """List issues in a repo (state: open|closed|all). One issue per line."""
    try:
        data = _gh_api(f"repos/{repo}/issues?state={state}&per_page=20")
    except GitHubError as e:
        return f"error: {e}"
    # The issues endpoint also returns PRs; drop them.
    issues = [i for i in data if "pull_request" not in i]
    if not issues:
        return f"no {state} issues in {repo}"
    return "\n".join(f"#{i['number']} {i['title']} ({i['state']})" for i in issues)


@tool
def get_issue(repo: str, number: int) -> str:
    """Get one issue's title, state, and body. ``repo`` is 'owner/name'."""
    try:
        i = _gh_api(f"repos/{repo}/issues/{number}")
    except GitHubError as e:
        return f"error: {e}"
    body = (i.get("body") or "").strip()
    return f"#{i['number']} {i['title']} [{i['state']}]\n{body}"


@tool
def comment_on_issue(repo: str, number: int, body: str) -> str:
    """Add a comment to an issue or PR. ``repo`` is 'owner/name'. Returns the URL."""
    try:
        c = _gh_api(
            f"repos/{repo}/issues/{number}/comments",
            method="POST",
            fields={"body": body},
        )
    except GitHubError as e:
        return f"error: {e}"
    return f"commented on #{number}: {c['html_url']}"


@tool
def list_pull_requests(repo: str, state: str = "open") -> str:
    """List pull requests in a repo (state: open|closed|all). One PR per line."""
    try:
        data = _gh_api(f"repos/{repo}/pulls?state={state}&per_page=20")
    except GitHubError as e:
        return f"error: {e}"
    if not data:
        return f"no {state} pull requests in {repo}"
    return "\n".join(f"#{p['number']} {p['title']} ({p['state']})" for p in data)


def all_tools() -> list:
    """Return every GitHub tool, ready to pass to ``Agent.act_with_tools``."""
    return [
        create_issue,
        list_issues,
        get_issue,
        comment_on_issue,
        list_pull_requests,
    ]
