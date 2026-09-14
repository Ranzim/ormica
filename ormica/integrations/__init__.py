"""First-party integrations — batteries you can hand to agents as tools.

Each integration is a module of ``@tool`` functions plus an ``all_tools()``
accessor. Import the one you need and pass its tools to an agent::

    from ormica.integrations.data import github

    agent.act_with_tools(prompt, tools=github.all_tools())

Sub-packages group integrations by kind:

- ``data`` — external systems of record (GitHub, …)
- ``communication`` — messaging (email, Slack, …)
- ``memory_backends`` — persistence backends for the mycelium
- ``llm`` — provider-specific brain helpers
"""
