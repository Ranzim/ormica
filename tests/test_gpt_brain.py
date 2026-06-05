"""Tests for GPTBrain — uses an injected fake client; no network."""
from dataclasses import dataclass, field
from typing import Optional

from ormica.brain import Brain, Message
from ormica.brain.gpt import GPTBrain


# --- Fake shapes mimicking the openai SDK response objects -------------------


@dataclass
class FakeMessage:
    content: Optional[str] = ""


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


class FakeChatCompletions:
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
        self.completions = FakeChatCompletions()


class FakeOpenAI:
    def __init__(self) -> None:
        self.chat = FakeChat()


def _cortex(**kw) -> tuple[GPTBrain, FakeOpenAI]:
    fake = FakeOpenAI()
    return GPTBrain(client=fake, **kw), fake


# --- Protocol conformance -----------------------------------------------------


def test_satisfies_cortex_protocol():
    brain, _ = _cortex()
    assert isinstance(brain, Brain)


def test_lazy_export_via_cortex_namespace():
    """``ormica.brain.GPTBrain`` resolves via lazy ``__getattr__``."""
    from ormica import brain as cortex_mod

    assert cortex_mod.GPTBrain is GPTBrain


# --- Request shaping ----------------------------------------------------------


def test_string_prompt_becomes_single_user_message():
    brain, fake = _cortex()
    brain.think("hello")
    assert fake.chat.completions.calls[0]["messages"] == [
        {"role": "user", "content": "hello"}
    ]


def test_message_list_passes_through_in_order():
    brain, fake = _cortex()
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


def test_system_prompt_becomes_first_system_role_message():
    brain, fake = _cortex()
    brain.think("hi", system="be terse")
    msgs = fake.chat.completions.calls[0]["messages"]
    assert msgs[0] == {"role": "system", "content": "be terse"}
    assert msgs[1] == {"role": "user", "content": "hi"}


def test_system_omitted_when_none_or_empty():
    brain, fake = _cortex()
    brain.think("hi")
    brain.think("hi", system="")
    for call in fake.chat.completions.calls:
        assert call["messages"][0]["role"] != "system"


def test_max_tokens_propagates_to_api_call():
    brain, fake = _cortex()
    brain.think("hi", max_tokens=2048)
    assert fake.chat.completions.calls[0]["max_tokens"] == 2048


def test_default_model_is_gpt_4o():
    brain, fake = _cortex()
    brain.think("hi")
    assert fake.chat.completions.calls[0]["model"] == "gpt-4o"


def test_custom_model_is_used():
    brain, fake = _cortex(model="gpt-4o-mini")
    brain.think("hi")
    assert fake.chat.completions.calls[0]["model"] == "gpt-4o-mini"


def test_no_function_calling_or_streaming_params_sent():
    """Thin adapter — tools/functions/stream are caller-side concerns."""
    brain, fake = _cortex()
    brain.think("hi")
    call = fake.chat.completions.calls[0]
    for forbidden in ("tools", "tool_choice", "functions", "function_call", "stream"):
        assert forbidden not in call


def test_no_sampling_parameters_sent():
    brain, fake = _cortex()
    brain.think("hi")
    call = fake.chat.completions.calls[0]
    for forbidden in ("temperature", "top_p", "presence_penalty", "frequency_penalty"):
        assert forbidden not in call


# --- Response extraction ------------------------------------------------------


def test_text_extracted_from_first_choice():
    brain, fake = _cortex()
    fake.chat.completions.next_response = FakeChatCompletion(
        choices=[FakeChoice(message=FakeMessage(content="the answer"))],
        usage=FakeUsage(prompt_tokens=3, completion_tokens=2),
    )
    assert brain.think("hi").content == "the answer"


def test_none_content_becomes_empty_string():
    """OpenAI returns None when only tool calls are present — we don't crash."""
    brain, fake = _cortex()
    fake.chat.completions.next_response = FakeChatCompletion(
        choices=[FakeChoice(message=FakeMessage(content=None))],
        usage=FakeUsage(prompt_tokens=1, completion_tokens=0),
    )
    assert brain.think("hi").content == ""


def test_tokens_used_sums_prompt_and_completion():
    brain, fake = _cortex()
    fake.chat.completions.next_response = FakeChatCompletion(
        choices=[FakeChoice(message=FakeMessage(content="x"))],
        usage=FakeUsage(prompt_tokens=100, completion_tokens=50),
    )
    assert brain.think("hi").tokens_used == 150


def test_missing_usage_yields_zero_tokens():
    brain, fake = _cortex()
    fake.chat.completions.next_response = FakeChatCompletion(
        choices=[FakeChoice(message=FakeMessage(content="x"))],
        usage=None,
    )
    assert brain.think("hi").tokens_used == 0


def test_finish_reason_propagated_from_choice():
    brain, fake = _cortex()
    fake.chat.completions.next_response = FakeChatCompletion(
        choices=[
            FakeChoice(message=FakeMessage(content="x"), finish_reason="length")
        ],
        usage=FakeUsage(prompt_tokens=1, completion_tokens=1),
    )
    assert brain.think("hi").finish_reason == "length"


def test_response_carries_configured_model_name():
    brain, fake = _cortex(model="gpt-5")
    fake.chat.completions.next_response = FakeChatCompletion(
        choices=[FakeChoice(message=FakeMessage(content="x"))],
        usage=FakeUsage(prompt_tokens=1, completion_tokens=1),
    )
    assert brain.think("hi").model == "gpt-5"


def test_raw_response_attached_for_callers_who_need_it():
    brain, fake = _cortex()
    api_resp = FakeChatCompletion(
        choices=[FakeChoice(message=FakeMessage(content="x"))],
        usage=FakeUsage(prompt_tokens=1, completion_tokens=1),
    )
    fake.chat.completions.next_response = api_resp
    assert brain.think("hi").raw is api_resp
