"""Tests for sandboxed tool execution."""
import os

import pytest

from ormica import Agent
from ormica.arbor import Tree
from ormica.brain import MockBrain, Tool, ToolCall
from ormica.sandbox import (
    Sandbox,
    SandboxError,
    SandboxLimits,
    command_tool,
    python_tool,
)

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="sandbox targets POSIX (resource limits, preexec)"
)


# --- config -------------------------------------------------------------------


def test_limits_validation():
    with pytest.raises(ValueError):
        SandboxLimits(timeout_sec=0)
    with pytest.raises(ValueError):
        SandboxLimits(max_output_bytes=0)


# --- run_python ---------------------------------------------------------------


def test_run_python_captures_stdout():
    r = Sandbox().run_python("print(2 + 3)")
    assert r.ok
    assert r.stdout.strip() == "5"
    assert r.returncode == 0


def test_run_python_nonzero_exit_on_error():
    r = Sandbox().run_python("raise ValueError('boom')")
    assert not r.ok
    assert r.returncode != 0
    assert "ValueError" in r.stderr


def test_timeout_kills_long_running_code():
    box = Sandbox(SandboxLimits(timeout_sec=0.5, max_cpu_sec=2))
    r = box.run_python("while True:\n    pass")
    assert r.timed_out
    assert r.returncode is None


def test_output_is_truncated():
    box = Sandbox(SandboxLimits(max_output_bytes=100))
    r = box.run_python("print('x' * 5000)")
    assert r.truncated
    assert len(r.stdout) < 5000
    assert "truncated" in r.stdout


def test_parent_env_secrets_not_visible(monkeypatch):
    monkeypatch.setenv("ORMICA_SECRET_TOKEN", "super-secret")
    r = Sandbox().run_python(
        "import os; print(os.environ.get('ORMICA_SECRET_TOKEN', 'MISSING'))"
    )
    assert r.stdout.strip() == "MISSING"


def test_allow_env_forwards_named_vars(monkeypatch):
    monkeypatch.setenv("ORMICA_ALLOWED", "yes")
    box = Sandbox(allow_env=["ORMICA_ALLOWED"])
    r = box.run_python("import os; print(os.environ.get('ORMICA_ALLOWED', 'MISSING'))")
    assert r.stdout.strip() == "yes"


def test_runs_in_isolated_tempdir():
    r = Sandbox().run_python("import os; print(os.getcwd())")
    assert r.stdout.strip() != os.getcwd()  # not the caller's directory


# --- run (argv) ---------------------------------------------------------------


def test_run_command_no_shell_expansion():
    # $HOME must NOT be expanded — proves there is no shell.
    tool = command_tool()
    out = tool(command="echo $HOME")
    assert "$HOME" in out


def test_run_empty_argv_raises():
    with pytest.raises(SandboxError):
        Sandbox().run([])


def test_run_unknown_command_raises():
    with pytest.raises(SandboxError, match="not found"):
        Sandbox().run(["definitely-not-a-real-binary-xyz"])


# --- tools --------------------------------------------------------------------


def test_python_tool_shape_and_run():
    tool = python_tool()
    assert isinstance(tool, Tool)
    assert tool.name == "run_python"
    assert tool.schema["required"] == ["code"]
    out = tool(code="print('hi')")
    assert "hi" in out and "exit=0" in out


def test_command_tool_parse_error_returned():
    out = command_tool()(command='echo "unterminated')
    assert out.startswith("[error]")


def test_agent_uses_python_tool():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "analyst")
    brain = MockBrain(
        replies=[
            [ToolCall(id="t1", name="run_python",
                      arguments={"code": "print(6 * 7)"})],
            "the answer is 42",
        ]
    )
    agent = Agent(node, brain)
    resp = agent.act_with_tools("compute 6*7", tools=[python_tool()])
    assert resp.content == "the answer is 42"
    tool_msg = next(m for m in brain.calls[1] if m.role == "tool")
    assert "42" in tool_msg.content
