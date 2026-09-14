"""Tests for the GitHub integration.

The `gh` transport is mocked throughout — these tests never touch the
network or require gh to be installed.
"""
from types import SimpleNamespace

import pytest

from ormica import Agent
from ormica.arbor import Tree
from ormica.brain import MockBrain, Tool, ToolCall
from ormica.integrations.data import github
from ormica.integrations.data.github import GitHubError


@pytest.fixture(autouse=True)
def _gh_available(monkeypatch):
    """Pretend `gh` is installed for every test unless overridden."""
    monkeypatch.setattr(github.shutil, "which", lambda _: "/usr/bin/gh")


def _fake_run(*, stdout="", returncode=0, stderr=""):
    """Build a subprocess.run replacement that records the args it received."""

    def run(args, capture_output, text):
        run.args = args
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    return run


# --- transport ----------------------------------------------------------------


def test_gh_api_builds_post_args_and_parses_json(monkeypatch):
    fake = _fake_run(stdout='{"number": 7}')
    monkeypatch.setattr(github.subprocess, "run", fake)

    data = github._gh_api(
        "repos/o/n/issues", method="POST", fields={"title": "hi", "body": "b"}
    )

    assert data == {"number": 7}
    assert fake.args == [
        "/usr/bin/gh", "api", "-X", "POST", "repos/o/n/issues",
        "-f", "title=hi", "-f", "body=b",
    ]


def test_gh_api_missing_binary_raises(monkeypatch):
    monkeypatch.setattr(github.shutil, "which", lambda _: None)
    with pytest.raises(GitHubError, match="not installed"):
        github._gh_api("repos/o/n/issues")


def test_gh_api_auth_error_raises(monkeypatch):
    fake = _fake_run(returncode=1, stderr="gh auth login required")
    monkeypatch.setattr(github.subprocess, "run", fake)
    with pytest.raises(GitHubError, match="not authenticated"):
        github._gh_api("repos/o/n/issues")


# --- tools --------------------------------------------------------------------


def test_create_issue_returns_url(monkeypatch):
    fake = _fake_run(
        stdout='{"number": 42, "html_url": "https://github.com/o/n/issues/42"}'
    )
    monkeypatch.setattr(github.subprocess, "run", fake)
    out = github.create_issue(repo="o/n", title="Bug", body="broken")
    assert out == "#42 created: https://github.com/o/n/issues/42"


def test_list_issues_excludes_pull_requests(monkeypatch):
    fake = _fake_run(
        stdout=(
            '[{"number": 1, "title": "real issue", "state": "open"},'
            ' {"number": 2, "title": "a PR", "state": "open",'
            '  "pull_request": {"url": "x"}}]'
        )
    )
    monkeypatch.setattr(github.subprocess, "run", fake)
    out = github.list_issues(repo="o/n")
    assert out == "#1 real issue (open)"


def test_list_issues_empty(monkeypatch):
    monkeypatch.setattr(github.subprocess, "run", _fake_run(stdout="[]"))
    assert github.list_issues(repo="o/n", state="closed") == "no closed issues in o/n"


def test_get_issue_formats_body(monkeypatch):
    fake = _fake_run(
        stdout='{"number": 3, "title": "T", "state": "open", "body": "hello\\n"}'
    )
    monkeypatch.setattr(github.subprocess, "run", fake)
    assert github.get_issue(repo="o/n", number=3) == "#3 T [open]\nhello"


def test_comment_on_issue_returns_url(monkeypatch):
    fake = _fake_run(
        stdout='{"html_url": "https://github.com/o/n/issues/3#issuecomment-9"}'
    )
    monkeypatch.setattr(github.subprocess, "run", fake)
    out = github.comment_on_issue(repo="o/n", number=3, body="thanks")
    assert out == "commented on #3: https://github.com/o/n/issues/3#issuecomment-9"


def test_tool_returns_error_string_on_api_failure(monkeypatch):
    fake = _fake_run(returncode=1, stderr="Not Found")
    monkeypatch.setattr(github.subprocess, "run", fake)
    out = github.create_issue(repo="o/nope", title="x")
    assert out.startswith("error:")
    assert "Not Found" in out


# --- packaging as tools -------------------------------------------------------


def test_all_tools_are_tool_instances_with_schemas():
    tools = github.all_tools()
    assert len(tools) == 5
    assert all(isinstance(t, Tool) for t in tools)
    names = {t.name for t in tools}
    assert names == {
        "create_issue", "list_issues", "get_issue",
        "comment_on_issue", "list_pull_requests",
    }
    create = next(t for t in tools if t.name == "create_issue")
    assert create.schema["required"] == ["repo", "title"]


# --- end-to-end through an agent ----------------------------------------------


def test_agent_uses_github_tool(monkeypatch):
    fake = _fake_run(
        stdout='{"number": 5, "html_url": "https://github.com/o/n/issues/5"}'
    )
    monkeypatch.setattr(github.subprocess, "run", fake)

    tree = Tree("HQ")
    node = tree.spawn(tree.root, "maintainer")
    brain = MockBrain(
        replies=[
            [ToolCall(id="t1", name="create_issue",
                      arguments={"repo": "o/n", "title": "Flaky CI"})],
            "Opened issue #5.",
        ]
    )
    agent = Agent(node, brain)
    response = agent.act_with_tools("File the flaky CI bug", tools=github.all_tools())

    assert response.content == "Opened issue #5."
    tool_msg = next(m for m in brain.calls[1] if m.role == "tool")
    assert "#5 created" in tool_msg.content
