# MCP bridge

Ormica speaks the Model Context Protocol in both directions, so it plugs into the
wider tool ecosystem and can also be driven by any MCP client.

## Consume any MCP server as tools

Point a colony at an MCP server and its tools become ordinary Ormica tools that
agents can call. No per integration code.

```python
import sys
from ormica.mcp import MCPClient

with MCPClient([sys.executable, "-m", "some_mcp_server"]) as mcp:
    tools = mcp.as_tools()
    agent = org.agent("worker", brain=brain)
    agent.act_with_tools("Fetch the latest ticket and summarize it", tools=tools)
```

`MCPClient` spawns the server as a subprocess, does the handshake, lists its
tools, and wraps each one as an Ormica `Tool`. You can also call tools directly
with `mcp.call(name, arguments)`.

## Expose a colony as an MCP server

Run a whole colony as a tool that any MCP client, including Claude, can call.
This is Ormica as a super tool: a single agent hands genuinely complex work to a
governed, audited coordination engine.

```bash
python -m ormica.mcp
```

It uses a real brain if a key is set (Gemini, then Claude), and a mock otherwise.
It exposes two tools:

- `ormica_ask(prompt)` runs one governed prompt through the colony.
- `ormica_solve(goal)` decomposes a complex goal and returns a synthesized result.

To serve your own colony, call `serve_stdio`:

```python
from ormica import Ormica
from ormica.brain import ClaudeBrain
from ormica.mcp import serve_stdio

org = Ormica("support")
org.plant("saas_helpdesk")
serve_stdio(org, ClaudeBrain())
```

## Notes

The transport is newline delimited JSON-RPC 2.0 over stdio, implemented with the
standard library, so there is no extra dependency. It covers `initialize`,
`tools/list`, and `tools/call`, which is what a client needs to discover and run
tools. Resources and prompts are not implemented yet.
