"""GPTBrain — OpenAI SDK adapter for the Brain protocol."""
from __future__ import annotations

import json
from typing import Any, Optional

from .protocol import Prompt, to_messages
from .tool import Tool, ToolCall
from .types import Response

DEFAULT_MODEL = "gpt-4o"


def _tools_to_openai(tools: Optional[list[Tool]]) -> Optional[list[dict]]:
    if not tools:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.schema,
            },
        }
        for t in tools
    ]


def _openai_messages(prompt: Prompt, *, system: Optional[str]) -> list[dict]:
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    for m in to_messages(prompt):
        if m.role == "tool":
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "content": m.content,
                }
            )
            continue
        if m.role == "assistant" and m.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments),
                            },
                        }
                        for call in m.tool_calls
                    ],
                }
            )
            continue
        messages.append({"role": m.role, "content": m.content})
    return messages


def _openai_response_to_internal(api_response: Any, model: str) -> Response:
    choice = api_response.choices[0]
    content = choice.message.content or ""
    tool_calls: list[ToolCall] = []
    raw_calls = getattr(choice.message, "tool_calls", None) or []
    for call in raw_calls:
        args = call.function.arguments
        try:
            parsed = json.loads(args) if isinstance(args, str) else dict(args)
        except json.JSONDecodeError:
            parsed = {"_raw": args}
        tool_calls.append(ToolCall(id=call.id, name=call.function.name, arguments=parsed))
    usage = api_response.usage
    tokens_used = (
        (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)
        if usage is not None
        else 0
    )
    return Response(
        content=content,
        model=model,
        tokens_used=tokens_used,
        finish_reason=choice.finish_reason or "",
        tool_calls=tool_calls,
        raw=api_response,
    )


class GPTBrain:
    """A thin sync adapter over the OpenAI Chat Completions API.

    Implements the :class:`Brain` protocol. The ``openai`` SDK is imported
    lazily so the rest of brain stays usable without the optional dependency.
    Install with: ``pip install ormica[openai]``.

    Intentionally minimal: no function calling, no streaming, no temperature
    knob. Layer those on top when a caller actually needs them — this
    adapter's job is one round trip per ``think()``.
    """

    name = "openai"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ImportError(
                    "GPTBrain needs the openai SDK. "
                    "Install with: pip install ormica[openai]"
                ) from exc
            client = OpenAI(api_key=api_key)
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
            "messages": _openai_messages(prompt, system=system),
            "max_tokens": max_tokens,
        }
        openai_tools = _tools_to_openai(tools)
        if openai_tools:
            kwargs["tools"] = openai_tools
        api_response = self.client.chat.completions.create(**kwargs)
        return _openai_response_to_internal(api_response, self.model)


class AsyncGPTBrain:
    """Async sibling of :class:`GPTBrain` — uses ``openai.AsyncOpenAI``."""

    name = "async-openai"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise ImportError(
                    "AsyncGPTBrain needs the openai SDK. "
                    "Install with: pip install ormica[openai]"
                ) from exc
            client = AsyncOpenAI(api_key=api_key)
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
            "messages": _openai_messages(prompt, system=system),
            "max_tokens": max_tokens,
        }
        openai_tools = _tools_to_openai(tools)
        if openai_tools:
            kwargs["tools"] = openai_tools
        api_response = await self.client.chat.completions.create(**kwargs)
        return _openai_response_to_internal(api_response, self.model)
