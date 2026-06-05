"""Brain value types — Message, Response, TokenBudget."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Message:
    """A single conversation turn.

    ``role`` is ``user`` | ``assistant`` | ``system`` | ``tool``.
    ``tool_calls`` is set on assistant turns that requested tool execution.
    ``tool_call_id`` is set on tool-result turns (``role == "tool"``) to
    link the result back to the call.
    """

    role: str
    content: str
    tool_calls: tuple = ()  # tuple[ToolCall, ...] — tuple for frozen-dataclass hashability
    tool_call_id: str = ""


@dataclass
class Response:
    """The result of a brain think call."""

    content: str
    model: str = ""
    tokens_used: int = 0
    finish_reason: str = ""
    tool_calls: list = field(default_factory=list)  # list[ToolCall]
    raw: Any = field(default=None, repr=False)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class BudgetExhausted(Exception):
    """Raised when a TokenBudget refuses a request."""


@dataclass
class TokenBudget:
    """Tracks token spend against a fixed limit."""

    limit: int
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit

    def can_afford(self, tokens: int) -> bool:
        return self.used + tokens <= self.limit

    def consume(self, tokens: int) -> None:
        if tokens < 0:
            raise ValueError("tokens cannot be negative")
        self.used += tokens
