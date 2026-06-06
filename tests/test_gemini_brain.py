"""Tests for GeminiBrain — uses an injected fake client; no Google SDK needed."""
from dataclasses import dataclass, field
from typing import Optional

import pytest

from ormica.brain import Brain, Message, ToolCall, tool
from ormica.brain.gemini import AsyncGeminiBrain, GeminiBrain


# --- Fake shapes mimicking the google-generativeai response objects ----------


@dataclass
class FakeFunctionCall:
    name: str = ""
    args: dict = field(default_factory=dict)


@dataclass
class FakePart:
    text: Optional[str] = None
    function_call: Optional[FakeFunctionCall] = None


@dataclass
class FakeContent:
    parts: list = field(default_factory=list)


@dataclass
class FakeCandidate:
    content: FakeContent = field(default_factory=FakeContent)
    finish_reason: str = "STOP"


@dataclass
class FakeUsageMetadata:
    prompt_token_count: int = 0
    candidates_token_count: int = 0


@dataclass
class FakeGenerateContentResponse:
    candidates: list = field(default_factory=list)
    usage_metadata: Optional[FakeUsageMetadata] = field(default_factory=FakeUsageMetadata)


class FakeGenerativeModel:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.next_response = FakeGenerateContentResponse(
            candidates=[
                FakeCandidate(
                    content=FakeContent(parts=[FakePart(text="hi from gemini")]),
                )
            ],
            usage_metadata=FakeUsageMetadata(
                prompt_token_count=5, candidates_token_count=3
            ),
        )

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.next_response


def _brain(**kw) -> tuple[GeminiBrain, FakeGenerativeModel]:
    fake = FakeGenerativeModel()
    return GeminiBrain(client=fake, **kw), fake


# --- Protocol + export -------------------------------------------------------


def test_satisfies_brain_protocol():
    brain, _ = _brain()
    assert isinstance(brain, Brain)


def test_lazy_export_via_brain_namespace():
    from ormica import brain as brain_mod
    assert brain_mod.GeminiBrain is GeminiBrain
    assert brain_mod.AsyncGeminiBrain is AsyncGeminiBrain


# --- Request shaping --------------------------------------------------------


def test_string_prompt_becomes_user_role_content():
    brain, fake = _brain()
    brain.think("hello")
    contents = fake.calls[0]["contents"]
    assert contents == [{"role": "user", "parts": [{"text": "hello"}]}]


def test_assistant_role_becomes_model_role():
    """Gemini uses 'model', not 'assistant'."""
    brain, fake = _brain()
    msgs = [
        Message(role="user", content="hi"),
        Message(role="assistant", content="hello"),
        Message(role="user", content="how are you?"),
    ]
    brain.think(msgs)
    contents = fake.calls[0]["contents"]
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"
    assert contents[2]["role"] == "user"


def test_system_prompt_becomes_top_level_system_instruction():
    brain, fake = _brain()
    brain.think("hi", system="be terse")
    assert fake.calls[0]["system_instruction"] == "be terse"


def test_system_omitted_when_none_or_empty():
    brain, fake = _brain()
    brain.think("hi")
    brain.think("hi", system="")
    for call in fake.calls:
        assert "system_instruction" not in call


def test_max_tokens_in_generation_config():
    brain, fake = _brain()
    brain.think("hi", max_tokens=2048)
    assert fake.calls[0]["generation_config"] == {"max_output_tokens": 2048}


def test_default_model_is_gemini_2_flash():
    brain, _ = _brain()
    assert brain.model == "gemini-2.0-flash"


def test_custom_model_kept_on_brain():
    brain, _ = _brain(model="gemini-1.5-pro")
    assert brain.model == "gemini-1.5-pro"


def test_tools_translate_to_function_declarations():
    brain, fake = _brain()

    @tool
    def lookup(query: str) -> str:
        """Look something up."""
        return "x"

    brain.think("go", tools=[lookup])
    fn_decls = fake.calls[0]["tools"][0]["function_declarations"]
    assert fn_decls[0]["name"] == "lookup"
    assert fn_decls[0]["description"] == "Look something up."
    assert fn_decls[0]["parameters"]["properties"]["query"]["type"] == "string"


def test_empty_tools_list_not_forwarded():
    brain, fake = _brain()
    brain.think("go", tools=[])
    assert "tools" not in fake.calls[0]


# --- Response extraction ----------------------------------------------------


def test_text_extracted_from_first_candidate_first_part():
    brain, fake = _brain()
    fake.next_response = FakeGenerateContentResponse(
        candidates=[
            FakeCandidate(
                content=FakeContent(parts=[FakePart(text="the answer")]),
            )
        ],
        usage_metadata=FakeUsageMetadata(prompt_token_count=3, candidates_token_count=2),
    )
    assert brain.think("hi").content == "the answer"


def test_tokens_used_sums_prompt_and_candidate_tokens():
    brain, fake = _brain()
    fake.next_response = FakeGenerateContentResponse(
        candidates=[FakeCandidate(content=FakeContent(parts=[FakePart(text="x")]))],
        usage_metadata=FakeUsageMetadata(prompt_token_count=100, candidates_token_count=50),
    )
    assert brain.think("hi").tokens_used == 150


def test_missing_usage_metadata_yields_zero_tokens():
    brain, fake = _brain()
    fake.next_response = FakeGenerateContentResponse(
        candidates=[FakeCandidate(content=FakeContent(parts=[FakePart(text="x")]))],
        usage_metadata=None,
    )
    assert brain.think("hi").tokens_used == 0


def test_function_call_part_extracted_as_toolcall():
    brain, fake = _brain()
    fake.next_response = FakeGenerateContentResponse(
        candidates=[
            FakeCandidate(
                content=FakeContent(
                    parts=[
                        FakePart(
                            function_call=FakeFunctionCall(
                                name="get_weather",
                                args={"city": "Tokyo"},
                            )
                        )
                    ],
                ),
            )
        ],
        usage_metadata=FakeUsageMetadata(prompt_token_count=4, candidates_token_count=4),
    )
    resp = brain.think("weather?")
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "get_weather"
    assert resp.tool_calls[0].arguments == {"city": "Tokyo"}
    assert resp.wants_tools is True


def test_text_and_function_call_in_same_response():
    brain, fake = _brain()
    fake.next_response = FakeGenerateContentResponse(
        candidates=[
            FakeCandidate(
                content=FakeContent(
                    parts=[
                        FakePart(text="Looking that up..."),
                        FakePart(
                            function_call=FakeFunctionCall(
                                name="lookup", args={"q": "x"}
                            )
                        ),
                    ],
                )
            )
        ],
        usage_metadata=FakeUsageMetadata(prompt_token_count=2, candidates_token_count=3),
    )
    resp = brain.think("look x up")
    assert resp.content == "Looking that up..."
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "lookup"


def test_finish_reason_propagated():
    brain, fake = _brain()
    fake.next_response = FakeGenerateContentResponse(
        candidates=[
            FakeCandidate(
                content=FakeContent(parts=[FakePart(text="x")]),
                finish_reason="MAX_TOKENS",
            )
        ],
        usage_metadata=FakeUsageMetadata(prompt_token_count=1, candidates_token_count=1),
    )
    assert brain.think("hi").finish_reason == "MAX_TOKENS"


# --- Async sibling -----------------------------------------------------------


class FakeAsyncGenerativeModel:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.next_response = FakeGenerateContentResponse(
            candidates=[
                FakeCandidate(
                    content=FakeContent(parts=[FakePart(text="async gemini")])
                )
            ],
            usage_metadata=FakeUsageMetadata(
                prompt_token_count=2, candidates_token_count=2
            ),
        )

    async def generate_content_async(self, **kwargs):
        self.calls.append(kwargs)
        return self.next_response


@pytest.mark.asyncio
async def test_async_gemini_roundtrip():
    fake = FakeAsyncGenerativeModel()
    brain = AsyncGeminiBrain(client=fake, model="gemini-1.5-pro")
    resp = await brain.think("hi", system="be brief", max_tokens=128)

    assert resp.content == "async gemini"
    assert resp.tokens_used == 4
    call = fake.calls[0]
    assert call["system_instruction"] == "be brief"
    assert call["generation_config"] == {"max_output_tokens": 128}
    assert call["contents"] == [{"role": "user", "parts": [{"text": "hi"}]}]
