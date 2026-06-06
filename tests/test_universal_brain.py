"""Tests for UniversalBrain — the OpenAI-compatible adapter for any base_url."""
from dataclasses import dataclass, field
from typing import Optional

import pytest

from ormica.brain import Brain, Message, tool
from ormica.brain.universal import AsyncUniversalBrain, UniversalBrain


# --- Fake shapes mimicking the openai SDK response objects -------------------


@dataclass
class FakeMessage:
    content: Optional[str] = ""
    tool_calls: list = field(default_factory=list)


@dataclass
class FakeChoice:
    message: FakeMessage = field(default_factory=FakeMessage)
    finish_reason: str = "stop"


@dataclass
class FakeUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class FakeChatCompletion:
    choices: list = field(default_factory=list)
    usage: Optional[FakeUsage] = field(default_factory=FakeUsage)


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.next_response = FakeChatCompletion(
            choices=[FakeChoice(message=FakeMessage(content="hi"))],
            usage=FakeUsage(prompt_tokens=5, completion_tokens=2),
        )

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.next_response


class FakeChat:
    def __init__(self) -> None:
        self.completions = FakeCompletions()


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.chat = FakeChat()


def _brain(**kw) -> tuple[UniversalBrain, FakeOpenAIClient]:
    fake = FakeOpenAIClient()
    return UniversalBrain(client=fake, **kw), fake


# --- Protocol conformance + export -------------------------------------------


def test_satisfies_brain_protocol():
    brain, _ = _brain()
    assert isinstance(brain, Brain)


def test_lazy_export_via_brain_namespace():
    from ormica import brain as brain_mod
    assert brain_mod.UniversalBrain is UniversalBrain
    assert brain_mod.AsyncUniversalBrain is AsyncUniversalBrain


# --- base_url is exposed (the whole point) ----------------------------------


def test_base_url_kept_on_instance():
    fake = FakeOpenAIClient()
    brain = UniversalBrain(client=fake, base_url="http://localhost:11434/v1")
    assert brain.base_url == "http://localhost:11434/v1"


def test_default_model_is_gpt_4o():
    brain, fake = _brain()
    brain.think("hi")
    assert fake.chat.completions.calls[0]["model"] == "gpt-4o"


def test_custom_model_is_used():
    brain, fake = _brain(model="llama3.2")
    brain.think("hi")
    assert fake.chat.completions.calls[0]["model"] == "llama3.2"


# --- Request shaping (same as GPTBrain) -------------------------------------


def test_string_prompt_becomes_single_user_message():
    brain, fake = _brain()
    brain.think("hello")
    assert fake.chat.completions.calls[0]["messages"] == [
        {"role": "user", "content": "hello"}
    ]


def test_system_prompt_becomes_first_system_message():
    brain, fake = _brain()
    brain.think("hi", system="be terse")
    msgs = fake.chat.completions.calls[0]["messages"]
    assert msgs[0] == {"role": "system", "content": "be terse"}
    assert msgs[1] == {"role": "user", "content": "hi"}


def test_message_list_passes_through_in_order():
    brain, fake = _brain()
    msgs = [
        Message(role="user", content="a"),
        Message(role="assistant", content="b"),
        Message(role="user", content="c"),
    ]
    brain.think(msgs)
    assert fake.chat.completions.calls[0]["messages"] == [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
    ]


def test_max_tokens_propagates():
    brain, fake = _brain()
    brain.think("hi", max_tokens=2048)
    assert fake.chat.completions.calls[0]["max_tokens"] == 2048


def test_no_sampling_or_streaming_params_sent():
    brain, fake = _brain()
    brain.think("hi")
    call = fake.chat.completions.calls[0]
    for forbidden in ("temperature", "top_p", "top_k", "stream"):
        assert forbidden not in call


def test_tools_forwarded_as_function_definitions():
    brain, fake = _brain()

    @tool
    def lookup(query: str) -> str:
        """Look something up."""
        return "x"

    brain.think("go", tools=[lookup])
    call = fake.chat.completions.calls[0]
    assert call["tools"][0]["type"] == "function"
    assert call["tools"][0]["function"]["name"] == "lookup"


def test_empty_tools_list_not_forwarded():
    brain, fake = _brain()
    brain.think("go", tools=[])
    assert "tools" not in fake.chat.completions.calls[0]


# --- Response extraction (same as GPTBrain) ---------------------------------


def test_text_extracted_from_first_choice():
    brain, fake = _brain()
    fake.chat.completions.next_response = FakeChatCompletion(
        choices=[FakeChoice(message=FakeMessage(content="the answer"))],
        usage=FakeUsage(prompt_tokens=3, completion_tokens=2),
    )
    assert brain.think("hi").content == "the answer"


def test_none_content_becomes_empty_string():
    brain, fake = _brain()
    fake.chat.completions.next_response = FakeChatCompletion(
        choices=[FakeChoice(message=FakeMessage(content=None))],
        usage=FakeUsage(prompt_tokens=1, completion_tokens=0),
    )
    assert brain.think("hi").content == ""


def test_tokens_used_sums_prompt_and_completion():
    brain, fake = _brain()
    fake.chat.completions.next_response = FakeChatCompletion(
        choices=[FakeChoice(message=FakeMessage(content="x"))],
        usage=FakeUsage(prompt_tokens=100, completion_tokens=50),
    )
    assert brain.think("hi").tokens_used == 150


def test_tool_call_extracted_from_response():
    """OpenAI-compat tool calls land in our ToolCall dataclass."""
    from dataclasses import dataclass as _dc, field as _f
    @_dc
    class FakeFn:
        name: str = ""
        arguments: str = "{}"
    @_dc
    class FakeToolCall:
        id: str = ""
        function: FakeFn = _f(default_factory=FakeFn)

    brain, fake = _brain()
    fake.chat.completions.next_response = FakeChatCompletion(
        choices=[
            FakeChoice(
                message=FakeMessage(
                    content=None,
                    tool_calls=[
                        FakeToolCall(
                            id="call_xyz",
                            function=FakeFn(name="lookup", arguments='{"q":"acme"}'),
                        )
                    ],
                )
            )
        ],
        usage=FakeUsage(prompt_tokens=4, completion_tokens=4),
    )
    resp = brain.think("find acme")
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].id == "call_xyz"
    assert resp.tool_calls[0].name == "lookup"
    assert resp.tool_calls[0].arguments == {"q": "acme"}
    assert resp.wants_tools is True


# --- Async sibling -----------------------------------------------------------


class FakeAsyncCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.next_response = FakeChatCompletion(
            choices=[FakeChoice(message=FakeMessage(content="async hi"))],
            usage=FakeUsage(prompt_tokens=2, completion_tokens=2),
        )

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.next_response


class FakeAsyncChat:
    def __init__(self) -> None:
        self.completions = FakeAsyncCompletions()


class FakeAsyncOpenAIClient:
    def __init__(self) -> None:
        self.chat = FakeAsyncChat()


@pytest.mark.asyncio
async def test_async_universal_roundtrip():
    fake = FakeAsyncOpenAIClient()
    brain = AsyncUniversalBrain(client=fake, model="llama3.2",
                                 base_url="http://localhost:11434/v1")
    resp = await brain.think("hi", system="brief", max_tokens=256)

    assert resp.content == "async hi"
    assert resp.tokens_used == 4
    call = fake.chat.completions.calls[0]
    assert call["model"] == "llama3.2"
    assert call["messages"] == [
        {"role": "system", "content": "brief"},
        {"role": "user", "content": "hi"},
    ]
    assert brain.base_url == "http://localhost:11434/v1"
