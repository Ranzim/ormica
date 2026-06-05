"""MockBrain — a scripted brain for tests and demos. Sync + async variants."""
from __future__ import annotations

import inspect
from typing import Callable, Iterable, Optional, Union

from .protocol import Prompt, to_messages
from .tool import ToolCall
from .types import Message, Response


# Replies can be plain strings (text completions) or ToolCall lists (a turn
# that asks the harness to run one or more tools).
Reply = Union[str, list[ToolCall]]


def _build_response(reply: Reply, model: str) -> Response:
    """Turn a scripted reply (str or ToolCall list) into a Response."""
    if isinstance(reply, list):
        return Response(
            content="",
            model=model,
            tokens_used=max(1, sum(len(str(c.arguments)) // 4 for c in reply)),
            finish_reason="tool_use",
            tool_calls=list(reply),
        )
    return Response(
        content=reply,
        model=model,
        tokens_used=max(1, len(reply) // 4),
        finish_reason="stop",
    )


class MockBrain:
    """No LLM call — returns scripted replies and records every prompt.

    Configure with either ``replies`` (cycled in order) or ``reply_fn``
    (called with the normalized message list). A reply may be either a
    plain string (text completion) or a list of :class:`ToolCall`
    (a turn that requests tool execution). Records each invocation
    in ``.calls`` for test assertions; ``tools=`` passed to ``think``
    is recorded in ``.tools_seen``.
    """

    name = "mock"

    def __init__(
        self,
        replies: Optional[Iterable[Reply]] = None,
        *,
        reply_fn: Optional[Callable[[list[Message]], Reply]] = None,
        model: str = "mock",
    ) -> None:
        if replies is None and reply_fn is None:
            raise ValueError("Provide either replies or reply_fn")
        if replies is not None and reply_fn is not None:
            raise ValueError("Provide either replies or reply_fn, not both")

        self._replies: Optional[list[Reply]] = (
            list(replies) if replies is not None else None
        )
        self._reply_fn = reply_fn
        self._index = 0
        self.model = model
        self.calls: list[list[Message]] = []
        self.tools_seen: list[Optional[list]] = []

    def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,  # noqa: ARG002 — accepted to satisfy the protocol
        tools: Optional[list] = None,
    ) -> Response:
        messages = to_messages(prompt)
        if system:
            messages = [Message(role="system", content=system), *messages]
        self.calls.append(messages)
        self.tools_seen.append(tools)

        if self._reply_fn is not None:
            reply: Reply = self._reply_fn(messages)
        elif self._replies:
            reply = self._replies[self._index % len(self._replies)]
            self._index += 1
        else:
            reply = ""

        return _build_response(reply, self.model)


class AsyncMockBrain:
    """Async sibling of :class:`MockBrain`.

    Cycles through ``replies`` (strings or :class:`ToolCall` lists) or
    calls ``reply_fn`` (which may itself be a coroutine function).
    Records each invocation in ``calls`` and the ``tools=`` set in
    ``tools_seen``.
    """

    name = "async-mock"

    def __init__(
        self,
        replies: Optional[Iterable[Reply]] = None,
        *,
        reply_fn: Optional[Callable[[list[Message]], Reply]] = None,
        model: str = "mock",
    ) -> None:
        if replies is None and reply_fn is None:
            raise ValueError("Provide either replies or reply_fn")
        if replies is not None and reply_fn is not None:
            raise ValueError("Provide either replies or reply_fn, not both")

        self._replies: Optional[list[Reply]] = (
            list(replies) if replies is not None else None
        )
        self._reply_fn = reply_fn
        self._index = 0
        self.model = model
        self.calls: list[list[Message]] = []
        self.tools_seen: list[Optional[list]] = []

    async def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,  # noqa: ARG002
        tools: Optional[list] = None,
    ) -> Response:
        messages = to_messages(prompt)
        if system:
            messages = [Message(role="system", content=system), *messages]
        self.calls.append(messages)
        self.tools_seen.append(tools)

        if self._reply_fn is not None:
            result = self._reply_fn(messages)
            reply: Reply = await result if inspect.isawaitable(result) else result
        elif self._replies:
            reply = self._replies[self._index % len(self._replies)]
            self._index += 1
        else:
            reply = ""

        return _build_response(reply, self.model)
