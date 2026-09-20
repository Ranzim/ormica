"""RetryingBrain — bounded exponential backoff around any Brain.

Provider SDKs raise transient errors under load — rate limits (429), 5xx,
timeouts, dropped connections. Left unhandled, a single blip fails the task,
so a real multi-agent run against a live LLM dies the moment it hits a rate
limit. This wraps *any* :class:`Brain` / :class:`AsyncBrain` and retries
``think`` on transient failures with exponential backoff + jitter — no change
to the adapters, works for Claude / GPT / Gemini / Universal alike::

    from ormica.brain import ClaudeBrain, RetryingBrain
    brain = RetryingBrain(ClaudeBrain(), max_retries=4)
    org.run(brain=brain)

Non-transient errors (auth, bad request, …) are re-raised immediately.
"""
from __future__ import annotations

import asyncio
import random
import time
from typing import Any, Callable, Optional

from .protocol import Prompt
from .types import Response

# Substrings in an exception's class name that signal a transient condition.
_TRANSIENT_NAMES = (
    "ratelimit", "toomanyrequests", "timeout", "apitimeout", "apiconnection",
    "connectionerror", "serviceunavailable", "internalservererror", "overloaded",
    "servererror", "badgateway", "gatewaytimeout", "temporarilyunavailable",
)
_TRANSIENT_CODES = {408, 409, 429, 500, 502, 503, 504}


def _status_of(exc: BaseException) -> Optional[int]:
    for obj, attr in (
        (exc, "status_code"), (exc, "status"), (exc, "code"),
        (getattr(exc, "response", None), "status_code"),
    ):
        val = getattr(obj, attr, None)
        try:
            return int(val)
        except (TypeError, ValueError):
            continue
    return None


def default_is_transient(exc: BaseException) -> bool:
    """Heuristic: is this exception worth retrying? (Provider-SDK-agnostic.)"""
    name = type(exc).__name__.lower()
    if any(k in name for k in _TRANSIENT_NAMES):
        return True
    return _status_of(exc) in _TRANSIENT_CODES


def _backoff(attempt: int, base: float, cap: float, jitter: bool) -> float:
    delay = min(cap, base * (2 ** attempt))
    return delay * random.uniform(0.5, 1.5) if jitter else delay


class _RetryConfig:
    def __init__(
        self,
        inner: Any,
        max_retries: int,
        base_delay: float,
        max_delay: float,
        jitter: bool,
        is_transient: Optional[Callable[[BaseException], bool]],
        on_retry: Optional[Callable[[BaseException, int], None]],
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.inner = inner
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.is_transient = is_transient or default_is_transient
        self.on_retry = on_retry

    @property
    def name(self) -> str:
        return getattr(self.inner, "name", "retrying")

    @property
    def model(self) -> str:
        return getattr(self.inner, "model", "")

    def _should_retry(self, exc: BaseException, attempt: int) -> bool:
        return attempt < self.max_retries and self.is_transient(exc)

    def _delay(self, attempt: int) -> float:
        return _backoff(attempt, self.base_delay, self.max_delay, self.jitter)


class RetryingBrain(_RetryConfig):
    """Wrap a sync :class:`Brain`; retry ``think`` on transient errors."""

    def __init__(
        self,
        inner: Any,
        *,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 20.0,
        jitter: bool = True,
        is_transient: Optional[Callable[[BaseException], bool]] = None,
        on_retry: Optional[Callable[[BaseException, int], None]] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(inner, max_retries, base_delay, max_delay, jitter,
                         is_transient, on_retry)
        self._sleep = sleep

    def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tools: Optional[list] = None,
    ) -> Response:
        attempt = 0
        while True:
            try:
                return self.inner.think(
                    prompt, system=system, max_tokens=max_tokens, tools=tools
                )
            except Exception as exc:  # noqa: BLE001 — re-raised unless transient
                if not self._should_retry(exc, attempt):
                    raise
                if self.on_retry is not None:
                    self.on_retry(exc, attempt)
                self._sleep(self._delay(attempt))
                attempt += 1


class AsyncRetryingBrain(_RetryConfig):
    """Wrap an :class:`AsyncBrain`; retry ``think`` with async backoff."""

    def __init__(
        self,
        inner: Any,
        *,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 20.0,
        jitter: bool = True,
        is_transient: Optional[Callable[[BaseException], bool]] = None,
        on_retry: Optional[Callable[[BaseException, int], None]] = None,
        sleep: Optional[Callable[[float], Any]] = None,
    ) -> None:
        super().__init__(inner, max_retries, base_delay, max_delay, jitter,
                         is_transient, on_retry)
        self._sleep = sleep or asyncio.sleep

    async def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tools: Optional[list] = None,
    ) -> Response:
        attempt = 0
        while True:
            try:
                return await self.inner.think(
                    prompt, system=system, max_tokens=max_tokens, tools=tools
                )
            except Exception as exc:  # noqa: BLE001 — re-raised unless transient
                if not self._should_retry(exc, attempt):
                    raise
                if self.on_retry is not None:
                    self.on_retry(exc, attempt)
                await self._sleep(self._delay(attempt))
                attempt += 1
