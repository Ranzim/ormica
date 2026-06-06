"""GeminiBrain — adapter for Google's Gemini models via the native API.

Gemini's native API is different enough from OpenAI's that it gets its own
adapter (similar to how Anthropic Claude gets ClaudeBrain). If you'd rather
not install the Google SDK, Gemini is also accessible through OpenRouter via
:class:`UniversalBrain`.

Install:
    pip install ormica[gemini]

Usage::

    from ormica import Ormica
    from ormica.brain import GeminiBrain

    org = Ormica("My Co")
    org.run(brain=GeminiBrain(model="gemini-2.0-flash"))

Authentication: set ``GOOGLE_API_KEY`` (or ``GEMINI_API_KEY``) in your
environment, or pass ``api_key=`` to the constructor.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from .protocol import Prompt, to_messages
from .tool import Tool, ToolCall
from .types import Response

DEFAULT_MODEL = "gemini-2.0-flash"


def _tools_to_gemini(tools: Optional[list[Tool]]) -> Optional[list[dict]]:
    """Translate our Tool list into Gemini's function-declaration format."""
    if not tools:
        return None
    return [
        {
            "function_declarations": [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.schema,
                }
                for t in tools
            ]
        }
    ]


def _gemini_contents(prompt: Prompt) -> list[dict]:
    """Translate our Messages into Gemini's contents array.

    Gemini uses roles ``user`` and ``model`` (not ``assistant``), and tool
    results ride as ``function_response`` parts in a user-role message.
    """
    out: list[dict] = []
    for m in to_messages(prompt):
        if m.role == "tool":
            out.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "function_response": {
                                "name": m.tool_call_id or "",
                                "response": {"content": m.content},
                            }
                        }
                    ],
                }
            )
            continue
        if m.role == "assistant" and m.tool_calls:
            parts: list[dict] = []
            if m.content:
                parts.append({"text": m.content})
            for call in m.tool_calls:
                parts.append(
                    {
                        "function_call": {
                            "name": call.name,
                            "args": call.arguments,
                        }
                    }
                )
            out.append({"role": "model", "parts": parts})
            continue
        role = "model" if m.role == "assistant" else "user"
        out.append({"role": role, "parts": [{"text": m.content}]})
    return out


def _gemini_response_to_internal(api_response: Any, model: str) -> Response:
    """Convert a Gemini response (GenerateContentResponse-shaped) to our Response."""
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    candidates = getattr(api_response, "candidates", None) or []
    finish_reason = ""

    for i, cand in enumerate(candidates[:1]):  # take the first candidate
        if hasattr(cand, "finish_reason"):
            finish_reason = str(cand.finish_reason or "")
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        for j, part in enumerate(parts):
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)
            fc = getattr(part, "function_call", None)
            if fc is not None and getattr(fc, "name", None):
                args = getattr(fc, "args", None)
                if hasattr(args, "items"):  # google's MapComposite acts dict-like
                    parsed = dict(args)
                elif isinstance(args, str):
                    try:
                        parsed = json.loads(args)
                    except json.JSONDecodeError:
                        parsed = {"_raw": args}
                else:
                    parsed = {} if args is None else dict(args)
                tool_calls.append(
                    ToolCall(
                        id=f"call_{i}_{j}",
                        name=str(fc.name),
                        arguments=parsed,
                    )
                )

    usage = getattr(api_response, "usage_metadata", None)
    if usage is not None:
        tokens_used = int(getattr(usage, "prompt_token_count", 0) or 0) + int(
            getattr(usage, "candidates_token_count", 0) or 0
        )
    else:
        tokens_used = 0

    return Response(
        content="".join(text_parts),
        model=model,
        tokens_used=tokens_used,
        finish_reason=finish_reason,
        tool_calls=tool_calls,
        raw=api_response,
    )


class GeminiBrain:
    """Sync :class:`Brain` adapter for Google Gemini models.

    Defaults to ``gemini-2.0-flash``. Requires the ``google-generativeai``
    SDK; install with ``pip install ormica[gemini]``.

    Inject ``client`` for testing — anything with a ``generate_content``
    method that accepts ``contents=``, ``system_instruction=``,
    ``tools=``, and a generation-config kwarg works.
    """

    name = "gemini"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            try:
                import google.generativeai as genai  # type: ignore
            except ImportError as exc:
                raise ImportError(
                    "GeminiBrain needs the google-generativeai SDK. "
                    "Install with: pip install ormica[gemini]"
                ) from exc
            if api_key is not None:
                genai.configure(api_key=api_key)
            client = genai.GenerativeModel(model)
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
            "contents": _gemini_contents(prompt),
            "generation_config": {"max_output_tokens": max_tokens},
        }
        if system:
            kwargs["system_instruction"] = system
        gemini_tools = _tools_to_gemini(tools)
        if gemini_tools:
            kwargs["tools"] = gemini_tools

        api_response = self.client.generate_content(**kwargs)
        return _gemini_response_to_internal(api_response, self.model)


class AsyncGeminiBrain:
    """Async sibling of :class:`GeminiBrain`."""

    name = "async-gemini"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            try:
                import google.generativeai as genai  # type: ignore
            except ImportError as exc:
                raise ImportError(
                    "AsyncGeminiBrain needs the google-generativeai SDK. "
                    "Install with: pip install ormica[gemini]"
                ) from exc
            if api_key is not None:
                genai.configure(api_key=api_key)
            client = genai.GenerativeModel(model)
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
            "contents": _gemini_contents(prompt),
            "generation_config": {"max_output_tokens": max_tokens},
        }
        if system:
            kwargs["system_instruction"] = system
        gemini_tools = _tools_to_gemini(tools)
        if gemini_tools:
            kwargs["tools"] = gemini_tools

        api_response = await self.client.generate_content_async(**kwargs)
        return _gemini_response_to_internal(api_response, self.model)
