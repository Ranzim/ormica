"""ClaudeBrain — Anthropic SDK adapter for the Brain protocol."""
from __future__ import annotations

from typing import Any, Optional

from .protocol import Prompt, to_messages
from .tool import Tool, ToolCall
from .types import Message, Response

DEFAULT_MODEL = "claude-opus-4-7"


def _tools_to_claude(tools: Optional[list[Tool]]) -> Optional[list[dict]]:
    if not tools:
        return None
    return [
        {"name": t.name, "description": t.description, "input_schema": t.schema}
        for t in tools
    ]


def _claude_messages(prompt: Prompt) -> list[dict]:
    """Encode our Messages into Claude's content-block format, including tools."""
    out: list[dict] = []
    for m in to_messages(prompt):
        if m.role == "tool":
            # Tool result rides as a user turn with a tool_result block.
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id,
                            "content": m.content,
                        }
                    ],
                }
            )
            continue
        if m.role == "assistant" and m.tool_calls:
            blocks: list[dict] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for call in m.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                )
            out.append({"role": "assistant", "content": blocks})
            continue
        out.append({"role": m.role, "content": m.content})
    return out


def _claude_response_to_internal(api_response: Any, model: str) -> Response:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in api_response.content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text_parts.append(block.text)
        elif block_type == "tool_use":
            tool_calls.append(
                ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
            )
    usage = api_response.usage
    tokens_used = (usage.input_tokens or 0) + (usage.output_tokens or 0)
    return Response(
        content="".join(text_parts),
        model=model,
        tokens_used=tokens_used,
        finish_reason=api_response.stop_reason or "",
        tool_calls=tool_calls,
        raw=api_response,
    )


class ClaudeBrain:
    """A thin sync adapter over the Anthropic Claude API.

    Implements the :class:`Brain` protocol. The ``anthropic`` SDK is
    imported lazily so the rest of brain stays usable without the optional
    dependency. Install with: ``pip install ormica[claude]``.

    Intentionally minimal: no prompt caching, no extended thinking, no
    streaming, no sampling parameters. Layer those on top when a caller
    actually needs them — the right caching strategy in particular depends
    on what is reusable in the caller's workload.
    """

    name = "claude"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            try:
                from anthropic import Anthropic
            except ImportError as exc:
                raise ImportError(
                    "ClaudeBrain needs the anthropic SDK. "
                    "Install with: pip install ormica[claude]"
                ) from exc
            client = Anthropic(api_key=api_key)
        self.client = client
        self.model = model

    def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tools: Optional[list[Tool]] = None,
    ) -> Response:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": _claude_messages(prompt),
        }
        if system:
            kwargs["system"] = system
        claude_tools = _tools_to_claude(tools)
        if claude_tools:
            kwargs["tools"] = claude_tools

        api_response = self.client.messages.create(**kwargs)
        return _claude_response_to_internal(api_response, self.model)


class AsyncClaudeBrain:
    """Async sibling of :class:`ClaudeBrain` — uses ``anthropic.AsyncAnthropic``."""

    name = "async-claude"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:
                raise ImportError(
                    "AsyncClaudeBrain needs the anthropic SDK. "
                    "Install with: pip install ormica[claude]"
                ) from exc
            client = AsyncAnthropic(api_key=api_key)
        self.client = client
        self.model = model

    async def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tools: Optional[list[Tool]] = None,
    ) -> Response:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": _claude_messages(prompt),
        }
        if system:
            kwargs["system"] = system
        claude_tools = _tools_to_claude(tools)
        if claude_tools:
            kwargs["tools"] = claude_tools

        api_response = await self.client.messages.create(**kwargs)
        return _claude_response_to_internal(api_response, self.model)
