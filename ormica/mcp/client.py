"""Consume any MCP server as Ormica tools.

Point a colony at an MCP server (a subprocess speaking stdio JSON-RPC) and its
tools become ordinary Ormica ``@tool`` objects that agents can call. This plugs
the whole MCP ecosystem into a colony with no per-integration code.

    with MCPClient([sys.executable, "-m", "some_mcp_server"]) as mcp:
        tools = mcp.as_tools()
        agent.act_with_tools("do the thing", tools=tools)
"""
from __future__ import annotations

import json
import subprocess
from typing import Any, Optional

from ormica.brain.tool import Tool

PROTOCOL_VERSION = "2024-11-05"


class MCPClient:
    """A minimal MCP stdio client: spawn a server, list its tools, call them."""

    def __init__(self, command: list[str]) -> None:
        self.proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1,
        )
        self._id = 0
        self._initialized = False

    def _rpc(self, method: str, params: Optional[dict] = None, *, notify: bool = False) -> Any:
        assert self.proc.stdin and self.proc.stdout
        msg: dict = {"jsonrpc": "2.0", "method": method}
        if not notify:
            self._id += 1
            msg["id"] = self._id
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed the connection")
            resp = json.loads(line)
            if resp.get("id") == self._id:
                if "error" in resp:
                    raise RuntimeError(f"MCP error: {resp['error']}")
                return resp.get("result")

    def initialize(self) -> dict:
        result = self._rpc("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "ormica", "version": "0"},
        })
        self._rpc("notifications/initialized", notify=True)
        self._initialized = True
        return result

    def list_tools(self) -> list[dict]:
        if not self._initialized:
            self.initialize()
        return self._rpc("tools/list").get("tools", [])

    def call(self, name: str, arguments: dict) -> str:
        if not self._initialized:
            self.initialize()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        parts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        return "\n".join(parts)

    def as_tools(self) -> list[Tool]:
        """Wrap every remote tool as an Ormica :class:`~ormica.brain.Tool`."""
        tools = []
        for spec in self.list_tools():
            name = spec["name"]

            def fn(_name=name, **kwargs):
                return self.call(_name, kwargs)

            tools.append(Tool(
                name=name,
                description=spec.get("description", ""),
                fn=fn,
                schema=spec.get("inputSchema", {"type": "object", "properties": {}}),
            ))
        return tools

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            self.proc.kill()

    def __enter__(self) -> "MCPClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
