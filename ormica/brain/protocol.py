"""The Brain protocols — the seam every LLM adapter implements."""
from __future__ import annotations

from typing import Optional, Protocol, Union, runtime_checkable

from .types import Message, Response

Prompt = Union[str, list[Message]]


@runtime_checkable
class Brain(Protocol):
    """The sync pluggable thinking engine.

    Implementations: :class:`MockBrain` (built-in, no deps),
    :class:`ClaudeBrain`, :class:`GPTBrain`.
    """

    name: str

    def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tools: Optional[list] = None,
    ) -> Response: ...


@runtime_checkable
class AsyncBrain(Protocol):
    """The awaitable twin of :class:`Brain`.

    Implementations: :class:`AsyncMockBrain`, :class:`AsyncClaudeBrain`,
    :class:`AsyncGPTBrain`. Used by :class:`AsyncAgent` and
    :class:`AsyncTaskRunner` to fan out LLM calls concurrently.
    """

    name: str

    async def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tools: Optional[list] = None,
    ) -> Response: ...


def to_messages(prompt: Prompt) -> list[Message]:
    """Normalize a string or message list into a list of Messages."""
    if isinstance(prompt, str):
        return [Message(role="user", content=prompt)]
    return list(prompt)
