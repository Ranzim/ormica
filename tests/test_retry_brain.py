"""Tests for RetryingBrain / AsyncRetryingBrain — transient-error backoff."""
import pytest

from ormica import Agent
from ormica.arbor import Tree
from ormica.brain import (
    AsyncRetryingBrain,
    Brain,
    RetryingBrain,
    default_is_transient,
)
from ormica.brain.types import Response


class RateLimitError(Exception):
    pass


class AuthError(Exception):
    pass


class _FlakyBrain:
    """Raises `exc` for the first `fails` calls, then returns a Response."""

    name = "flaky"
    model = "flaky-1"

    def __init__(self, fails, exc):
        self.fails = fails
        self.exc = exc
        self.calls = 0

    def think(self, prompt, *, system=None, max_tokens=1024, tools=None):
        self.calls += 1
        if self.calls <= self.fails:
            raise self.exc
        return Response(content="ok", model=self.model, tokens_used=1)


class _AsyncFlaky(_FlakyBrain):
    async def think(self, prompt, *, system=None, max_tokens=1024, tools=None):
        self.calls += 1
        if self.calls <= self.fails:
            raise self.exc
        return Response(content="ok", model=self.model, tokens_used=1)


# --- transient detection ------------------------------------------------------


def test_default_is_transient_by_name_and_code():
    assert default_is_transient(RateLimitError("429"))            # name match
    assert default_is_transient(TimeoutError("slow"))             # name match
    assert not default_is_transient(AuthError("bad key"))         # not transient

    class Boom(Exception):
        status_code = 503
    assert default_is_transient(Boom())                           # status code

    class Bad(Exception):
        status_code = 400
    assert not default_is_transient(Bad())


# --- sync retry ---------------------------------------------------------------


def test_retries_transient_then_succeeds():
    slept = []
    inner = _FlakyBrain(fails=2, exc=RateLimitError("429"))
    brain = RetryingBrain(inner, max_retries=3, jitter=False, sleep=slept.append)
    assert isinstance(brain, Brain)
    resp = brain.think("hi")
    assert resp.content == "ok"
    assert inner.calls == 3          # 2 failures + 1 success
    assert len(slept) == 2           # backed off twice
    assert slept[0] < slept[1]       # exponential


def test_gives_up_after_max_retries():
    inner = _FlakyBrain(fails=99, exc=RateLimitError("429"))
    brain = RetryingBrain(inner, max_retries=2, jitter=False, sleep=lambda _s: None)
    with pytest.raises(RateLimitError):
        brain.think("hi")
    assert inner.calls == 3          # initial + 2 retries


def test_non_transient_not_retried():
    inner = _FlakyBrain(fails=99, exc=AuthError("bad key"))
    brain = RetryingBrain(inner, max_retries=5, sleep=lambda _s: None)
    with pytest.raises(AuthError):
        brain.think("hi")
    assert inner.calls == 1          # failed fast, no retry


def test_on_retry_callback_and_passthrough():
    seen = []
    inner = _FlakyBrain(fails=1, exc=RateLimitError("429"))
    brain = RetryingBrain(inner, jitter=False, sleep=lambda _s: None,
                          on_retry=lambda exc, n: seen.append(n))
    brain.think("hi")
    assert seen == [0]
    assert brain.name == "flaky" and brain.model == "flaky-1"   # proxied


def test_works_end_to_end_through_agent():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    inner = _FlakyBrain(fails=1, exc=TimeoutError("slow"))
    agent = Agent(node, RetryingBrain(inner, jitter=False, sleep=lambda _s: None))
    assert agent.act("go").content == "ok"


def test_invalid_max_retries():
    with pytest.raises(ValueError):
        RetryingBrain(_FlakyBrain(0, None), max_retries=-1)


# --- async retry --------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_retries_then_succeeds():
    slept = []

    async def fake_sleep(d):
        slept.append(d)

    inner = _AsyncFlaky(fails=2, exc=RateLimitError("429"))
    brain = AsyncRetryingBrain(inner, jitter=False, sleep=fake_sleep)
    resp = await brain.think("hi")
    assert resp.content == "ok"
    assert inner.calls == 3
    assert len(slept) == 2


@pytest.mark.asyncio
async def test_async_non_transient_not_retried():
    inner = _AsyncFlaky(fails=99, exc=AuthError("nope"))
    brain = AsyncRetryingBrain(inner, sleep=lambda _d: None)
    with pytest.raises(AuthError):
        await brain.think("hi")
    assert inner.calls == 1
