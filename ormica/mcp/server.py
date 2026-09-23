"""Expose Ormica as an MCP server.

Any MCP client, including Claude, can then hand a hard goal to a whole colony and
get back a governed, audited result. This is Ormica as a super tool: a single
agent delegates genuinely complex work to a coordination engine.

Speaks minimal MCP over stdio: newline delimited JSON-RPC 2.0, no dependencies.
Run it with ``python -m ormica.mcp`` (uses a real brain if a key is present, a
mock otherwise), or embed :func:`serve_stdio` with your own colony.
"""
from __future__ import annotations

import json
import sys
from typing import Any

PROTOCOL_VERSION = "2024-11-05"


def _tools(org: Any, brain: Any) -> dict:
    return {
        "ormica_ask": {
            "description": "Run one governed prompt through an Ormica colony and return the answer.",
            "schema": {
                "type": "object",
                "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"],
            },
            "fn": lambda a: org.ask(a["prompt"], brain=brain),
        },
        "ormica_solve": {
            "description": "Give a colony a complex goal; it decomposes and delegates, and returns a synthesized result.",
            "schema": {
                "type": "object",
                "properties": {"goal": {"type": "string"}},
                "required": ["goal"],
            },
            "fn": lambda a: org.solve(a["goal"], brain=brain).content,
        },
    }


def _ok(mid: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(msg: dict, tools: dict) -> "dict | None":
    """Handle one JSON-RPC message. Returns a response dict, or None for notifications."""
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        from ormica import __version__
        return _ok(mid, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "ormica", "version": __version__},
        })
    if method == "tools/list":
        return _ok(mid, {"tools": [
            {"name": n, "description": t["description"], "inputSchema": t["schema"]}
            for n, t in tools.items()
        ]})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = tools.get(name)
        if tool is None:
            return _err(mid, -32602, f"unknown tool: {name!r}")
        try:
            text = tool["fn"](args)
            return _ok(mid, {"content": [{"type": "text", "text": str(text)}], "isError": False})
        except Exception as exc:  # noqa: BLE001 — surface tool errors as MCP tool errors
            return _ok(mid, {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True})

    if mid is None:
        return None                      # a notification (e.g. notifications/initialized)
    return _err(mid, -32601, f"method not found: {method!r}")


def serve_stdio(org: Any, brain: Any, *, in_stream=None, out_stream=None) -> None:
    """Serve an Ormica colony over stdio until the input closes."""
    in_stream = in_stream or sys.stdin
    out_stream = out_stream or sys.stdout
    tools = _tools(org, brain)
    for line in in_stream:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg, tools)
        if resp is not None:
            out_stream.write(json.dumps(resp) + "\n")
            out_stream.flush()


def main(argv=None) -> int:
    import os

    from ormica import Ormica

    org = Ormica("mcp-colony")
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        from ormica.brain.gemini import GeminiBrain
        from ormica.brain.retry import RetryingBrain
        brain: Any = RetryingBrain(GeminiBrain())
    elif os.environ.get("ANTHROPIC_API_KEY"):
        from ormica.brain import ClaudeBrain
        brain = ClaudeBrain()
    else:
        from ormica.brain import MockBrain
        brain = MockBrain(replies=["ok"])
    serve_stdio(org, brain)
    return 0
