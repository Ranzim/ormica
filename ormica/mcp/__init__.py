"""MCP bridge — both directions.

- Expose a colony as an MCP server so any client can drive it (:mod:`.server`).
- Consume any MCP server as Ormica tools (:class:`.client.MCPClient`).
"""
from .client import MCPClient
from .server import handle, serve_stdio

__all__ = ["MCPClient", "handle", "serve_stdio"]
