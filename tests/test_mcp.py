"""Tests for the MCP bridge — server handler (unit) + a real round trip."""
import sys
from types import SimpleNamespace

from ormica.mcp import MCPClient, handle
from ormica.mcp.server import _tools


def _fake_tools():
    org = SimpleNamespace(
        ask=lambda prompt, brain: f"echo:{prompt}",
        solve=lambda goal, brain: SimpleNamespace(content=f"solved:{goal}"),
    )
    return _tools(org, brain=object())


# --- server handler, no subprocess -------------------------------------------


def test_initialize_advertises_tools_capability():
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, _fake_tools())
    assert r["result"]["serverInfo"]["name"] == "ormica"
    assert "tools" in r["result"]["capabilities"]


def test_tools_list_exposes_ormica_tools():
    r = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, _fake_tools())
    names = {t["name"] for t in r["result"]["tools"]}
    assert {"ormica_ask", "ormica_solve"} <= names


def test_tools_call_runs_the_colony():
    tools = _fake_tools()
    r = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "ormica_ask", "arguments": {"prompt": "hi"}}}, tools)
    assert r["result"]["isError"] is False
    assert r["result"]["content"][0]["text"] == "echo:hi"


def test_unknown_tool_is_a_tool_error():
    r = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "nope", "arguments": {}}}, _fake_tools())
    assert "error" in r


def test_notification_gets_no_response():
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, _fake_tools()) is None


# --- real round trip: our client drives our server over stdio ----------------


def test_client_server_roundtrip():
    with MCPClient([sys.executable, "-m", "ormica.mcp"]) as mcp:
        info = mcp.initialize()
        assert info["serverInfo"]["name"] == "ormica"
        names = {t["name"] for t in mcp.list_tools()}
        assert "ormica_ask" in names
        out = mcp.call("ormica_ask", {"prompt": "hello"})
        assert out == "ok"                     # server falls back to MockBrain offline
        # and the remote tools wrap as ormica Tools
        tools = mcp.as_tools()
        assert any(t.name == "ormica_solve" for t in tools)
