"""Tests for AsyncBrain protocol + AsyncMockBrain + async adapters."""
import asyncio
from dataclasses import dataclass, field
from typing import Optional

import pytest

from ormica.brain import AsyncBrain, AsyncMockBrain, Message


# --- AsyncMockBrain ---------------------------------------------------------


@pytest.mark.asyncio
async def test_async_mock_satisfies_protocol():
    assert isinstance(AsyncMockBrain(replies=["x"]), AsyncBrain)


@pytest.mark.asyncio
async def test_async_mock_cycles_replies():
    brain = AsyncMockBrain(replies=["one", "two"])
    r1 = await brain.think("a")
    r2 = await brain.think("b")
    r3 = await brain.think("c")
    assert (r1.content, r2.content, r3.content) == ("one", "two", "one")


@pytest.mark.asyncio
async def test_async_mock_records_calls():
    brain = AsyncMockBrain(replies=["x"])
    await brain.think("hi", system="be brief")
    assert brain.calls[0][0].role == "system"
    assert brain.calls[0][1].role == "user"


@pytest.mark.asyncio
async def test_async_mock_accepts_sync_reply_fn():
    brain = AsyncMockBrain(reply_fn=lambda msgs: f"got {len(msgs)}")
    resp = await brain.think("hi")
    assert resp.content == "got 1"


@pytest.mark.asyncio
async def test_async_mock_accepts_async_reply_fn():
    async def aresponder(messages):
        await asyncio.sleep(0)
        return "from coroutine"

    brain = AsyncMockBrain(reply_fn=aresponder)
    resp = await brain.think("hi")
    assert resp.content == "from coroutine"


def test_async_mock_validation():
    with pytest.raises(ValueError):
        AsyncMockBrain()
    with pytest.raises(ValueError):
        AsyncMockBrain(replies=["x"], reply_fn=lambda _: "y")


# --- AsyncClaudeBrain (fake client) -----------------------------------------


@dataclass
class _ClaudeBlock:
    type: str
    text: str = ""


@dataclass
class _ClaudeUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class _ClaudeResponse:
    content: list = field(default_factory=list)
    usage: _ClaudeUsage = field(default_factory=_ClaudeUsage)
    stop_reason: str = "end_turn"


class _FakeAsyncClaudeMessages:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.next_response = _ClaudeResponse(
            content=[_ClaudeBlock(type="text", text="hello from async claude")],
            usage=_ClaudeUsage(input_tokens=5, output_tokens=3),
        )

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.next_response


class _FakeAsyncAnthropic:
    def __init__(self) -> None:
        self.messages = _FakeAsyncClaudeMessages()


@pytest.mark.asyncio
async def test_async_claude_roundtrip():
    from ormica.brain.claude import AsyncClaudeBrain

    fake = _FakeAsyncAnthropic()
    brain = AsyncClaudeBrain(client=fake)
    resp = await brain.think("hi", system="be brief", max_tokens=512)

    assert resp.content == "hello from async claude"
    assert resp.tokens_used == 8
    assert resp.finish_reason == "end_turn"
    call = fake.messages.calls[0]
    assert call["model"] == "claude-opus-4-7"
    assert call["max_tokens"] == 512
    assert call["system"] == "be brief"
    assert call["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_async_claude_satisfies_protocol():
    from ormica.brain.claude import AsyncClaudeBrain

    assert isinstance(AsyncClaudeBrain(client=_FakeAsyncAnthropic()), AsyncBrain)


# --- AsyncGPTBrain (fake client) --------------------------------------------


@dataclass
class _GPTMessage:
    content: Optional[str] = ""


@dataclass
class _GPTChoice:
    message: _GPTMessage = field(default_factory=_GPTMessage)
    finish_reason: str = "stop"


@dataclass
class _GPTUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class _GPTResponse:
    choices: list = field(default_factory=list)
    usage: Optional[_GPTUsage] = field(default_factory=_GPTUsage)


class _FakeAsyncCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.next_response = _GPTResponse(
            choices=[_GPTChoice(message=_GPTMessage(content="hello from async gpt"))],
            usage=_GPTUsage(prompt_tokens=4, completion_tokens=4),
        )

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.next_response


class _FakeAsyncChat:
    def __init__(self) -> None:
        self.completions = _FakeAsyncCompletions()


class _FakeAsyncOpenAI:
    def __init__(self) -> None:
        self.chat = _FakeAsyncChat()


@pytest.mark.asyncio
async def test_async_gpt_roundtrip():
    from ormica.brain.gpt import AsyncGPTBrain

    fake = _FakeAsyncOpenAI()
    brain = AsyncGPTBrain(client=fake, model="gpt-4o-mini")
    resp = await brain.think("hi", system="be brief", max_tokens=128)

    assert resp.content == "hello from async gpt"
    assert resp.tokens_used == 8
    assert resp.finish_reason == "stop"
    call = fake.chat.completions.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["max_tokens"] == 128
    assert call["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
    ]


@pytest.mark.asyncio
async def test_async_gpt_satisfies_protocol():
    from ormica.brain.gpt import AsyncGPTBrain

    assert isinstance(AsyncGPTBrain(client=_FakeAsyncOpenAI()), AsyncBrain)


# --- Lazy exports ------------------------------------------------------------


def test_async_adapters_exposed_via_cortex_namespace():
    from ormica import brain as cortex_mod
    from ormica.brain.claude import AsyncClaudeBrain
    from ormica.brain.gpt import AsyncGPTBrain

    assert cortex_mod.AsyncClaudeBrain is AsyncClaudeBrain
    assert cortex_mod.AsyncGPTBrain is AsyncGPTBrain
