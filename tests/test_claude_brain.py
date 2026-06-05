"""Tests for ClaudeBrain — uses an injected fake client; no network."""
from dataclasses import dataclass, field

from ormica.brain import Brain, Message
from ormica.brain.claude import ClaudeBrain


# --- Fake shapes mimicking the anthropic SDK response objects ---


@dataclass
class FakeBlock:
    type: str
    text: str = ""
    # tool_use blocks need these too — defaults keep text-only blocks ergonomic.
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class FakeAPIResponse:
    content: list = field(default_factory=list)
    usage: FakeUsage = field(default_factory=FakeUsage)
    stop_reason: str = "end_turn"


class FakeMessages:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.next_response = FakeAPIResponse(
            content=[FakeBlock(type="text", text="hi")],
            usage=FakeUsage(input_tokens=5, output_tokens=2),
        )

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.next_response


class FakeAnthropic:
    def __init__(self) -> None:
        self.messages = FakeMessages()


def _cortex(**kw) -> tuple[ClaudeBrain, FakeAnthropic]:
    fake = FakeAnthropic()
    return ClaudeBrain(client=fake, **kw), fake


# --- Protocol conformance ---


def test_satisfies_cortex_protocol():
    brain, _ = _cortex()
    assert isinstance(brain, Brain)


def test_lazy_export_via_cortex_namespace():
    """``ormica.brain.ClaudeBrain`` resolves via lazy ``__getattr__``."""
    from ormica import brain as cortex_mod

    assert cortex_mod.ClaudeBrain is ClaudeBrain


# --- Request shaping ---


def test_string_prompt_becomes_single_user_message():
    brain, fake = _cortex()
    brain.think("hello")
    assert fake.messages.calls[0]["messages"] == [
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
    assert fake.messages.calls[0]["messages"] == [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
    ]


def test_system_prompt_passed_as_top_level_kwarg():
    brain, fake = _cortex()
    brain.think("hi", system="be terse")
    assert fake.messages.calls[0]["system"] == "be terse"


def test_system_kwarg_omitted_when_none_or_empty():
    brain, fake = _cortex()
    brain.think("hi")
    brain.think("hi", system="")
    for call in fake.messages.calls:
        assert "system" not in call


def test_max_tokens_propagates_to_api_call():
    brain, fake = _cortex()
    brain.think("hi", max_tokens=2048)
    assert fake.messages.calls[0]["max_tokens"] == 2048


def test_default_model_is_claude_opus_4_7():
    brain, fake = _cortex()
    brain.think("hi")
    assert fake.messages.calls[0]["model"] == "claude-opus-4-7"


def test_custom_model_is_used():
    brain, fake = _cortex(model="claude-haiku-4-5")
    brain.think("hi")
    assert fake.messages.calls[0]["model"] == "claude-haiku-4-5"


def test_no_sampling_parameters_sent():
    """temperature/top_p/top_k 400 on Opus 4.7 — verify we don't send them."""
    brain, fake = _cortex()
    brain.think("hi")
    call = fake.messages.calls[0]
    assert "temperature" not in call
    assert "top_p" not in call
    assert "top_k" not in call


def test_no_thinking_or_caching_parameters_sent():
    """Thin adapter — extended thinking and caching are caller-side concerns."""
    brain, fake = _cortex()
    brain.think("hi")
    call = fake.messages.calls[0]
    assert "thinking" not in call
    assert "cache_control" not in call


# --- Response extraction ---


def test_text_blocks_concatenated_in_order():
    brain, fake = _cortex()
    fake.messages.next_response = FakeAPIResponse(
        content=[
            FakeBlock(type="text", text="hello "),
            FakeBlock(type="text", text="world"),
        ],
        usage=FakeUsage(input_tokens=3, output_tokens=2),
    )
    assert brain.think("hi").content == "hello world"


def test_non_text_blocks_skipped():
    brain, fake = _cortex()
    fake.messages.next_response = FakeAPIResponse(
        content=[
            FakeBlock(type="thinking", text="(reasoning hidden)"),
            FakeBlock(type="text", text="actual answer"),
            FakeBlock(type="tool_use", text=""),
        ],
        usage=FakeUsage(input_tokens=10, output_tokens=4),
    )
    assert brain.think("hi").content == "actual answer"


def test_tokens_used_sums_input_and_output():
    brain, fake = _cortex()
    fake.messages.next_response = FakeAPIResponse(
        content=[FakeBlock(type="text", text="x")],
        usage=FakeUsage(input_tokens=100, output_tokens=50),
    )
    assert brain.think("hi").tokens_used == 150


def test_finish_reason_propagated_from_stop_reason():
    brain, fake = _cortex()
    fake.messages.next_response = FakeAPIResponse(
        content=[FakeBlock(type="text", text="x")],
        usage=FakeUsage(input_tokens=1, output_tokens=1),
        stop_reason="max_tokens",
    )
    assert brain.think("hi").finish_reason == "max_tokens"


def test_response_carries_configured_model_name():
    brain, fake = _cortex(model="claude-sonnet-4-6")
    fake.messages.next_response = FakeAPIResponse(
        content=[FakeBlock(type="text", text="x")],
        usage=FakeUsage(input_tokens=1, output_tokens=1),
    )
    assert brain.think("hi").model == "claude-sonnet-4-6"


def test_raw_response_attached_for_callers_who_need_it():
    brain, fake = _cortex()
    api_resp = FakeAPIResponse(
        content=[FakeBlock(type="text", text="x")],
        usage=FakeUsage(input_tokens=1, output_tokens=1),
    )
    fake.messages.next_response = api_resp
    assert brain.think("hi").raw is api_resp
