"""Cross-brain conformance — the contract EVERY adapter must satisfy.

Per-adapter tests live in test_gpt_brain / test_claude_brain / test_gemini_brain /
test_universal_brain. This file centralizes the *shared guarantees* so that
"any brain works, tool calling included" is a verified, regression-proof claim
rather than a hope. Each provider family (OpenAI-compatible, Anthropic, Google)
is exercised through the same assertions with an injected fake client — no
network, no SDK keys.
"""
import json
from dataclasses import dataclass, field
from typing import Callable, Optional

import pytest

from ormica.brain import Brain, tool
from ormica.brain.claude import ClaudeBrain
from ormica.brain.gemini import GeminiBrain
from ormica.brain.gpt import GPTBrain
from ormica.brain.universal import UniversalBrain


@tool
def sample_tool(city: str) -> str:
    """A sample tool."""
    return city


# --- OpenAI-compatible family (GPTBrain, UniversalBrain, all providers) ------


@dataclass
class _OAIFn:
    name: str = ""
    arguments: str = "{}"


@dataclass
class _OAIToolCall:
    id: str = "call_1"
    function: _OAIFn = field(default_factory=_OAIFn)


@dataclass
class _OAIMessage:
    content: Optional[str] = ""
    tool_calls: list = field(default_factory=list)


@dataclass
class _OAIChoice:
    message: _OAIMessage = field(default_factory=_OAIMessage)
    finish_reason: str = "stop"


@dataclass
class _OAIUsage:
    prompt_tokens: int = 1
    completion_tokens: int = 1


@dataclass
class _OAICompletion:
    choices: list = field(default_factory=list)
    usage: Optional[_OAIUsage] = field(default_factory=_OAIUsage)


class _FakeOpenAI:
    def __init__(self):
        self.calls: list[dict] = []
        self.next = _OAICompletion(choices=[_OAIChoice(_OAIMessage(content="hi"))])

    class _Chat:
        def __init__(self, outer):
            self.completions = outer

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.next

    @property
    def chat(self):
        return _FakeOpenAI._Chat(self)


def _oai_set_text(fake, text):
    fake.next = _OAICompletion(choices=[_OAIChoice(_OAIMessage(content=text))])


def _oai_set_tool(fake, name, args):
    call = _OAIToolCall(function=_OAIFn(name=name, arguments=json.dumps(args)))
    fake.next = _OAICompletion(
        choices=[_OAIChoice(_OAIMessage(content=None, tool_calls=[call]),
                            finish_reason="tool_calls")]
    )


# --- Anthropic family --------------------------------------------------------


@dataclass
class _ClaudeBlock:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class _ClaudeUsage:
    input_tokens: int = 1
    output_tokens: int = 1


@dataclass
class _ClaudeResponse:
    content: list = field(default_factory=list)
    usage: _ClaudeUsage = field(default_factory=_ClaudeUsage)
    stop_reason: str = "end_turn"


class _FakeAnthropic:
    def __init__(self):
        self.calls: list[dict] = []
        self.next = _ClaudeResponse(content=[_ClaudeBlock("text", text="hi")])

    class _Messages:
        def __init__(self, outer):
            self.outer = outer

        def create(self, **kwargs):
            self.outer.calls.append(kwargs)
            return self.outer.next

    @property
    def messages(self):
        return _FakeAnthropic._Messages(self)


def _claude_set_text(fake, text):
    fake.next = _ClaudeResponse(content=[_ClaudeBlock("text", text=text)])


def _claude_set_tool(fake, name, args):
    fake.next = _ClaudeResponse(
        content=[_ClaudeBlock(type="tool_use", id="t1", name=name, input=args)],
        stop_reason="tool_use",
    )


# --- Google Gemini family ----------------------------------------------------


@dataclass
class _GemFn:
    name: str = ""
    args: dict = field(default_factory=dict)


@dataclass
class _GemPart:
    text: Optional[str] = None
    function_call: Optional[_GemFn] = None


@dataclass
class _GemContent:
    parts: list = field(default_factory=list)


@dataclass
class _GemCandidate:
    content: _GemContent = field(default_factory=_GemContent)
    finish_reason: str = "STOP"


@dataclass
class _GemUsage:
    prompt_token_count: int = 1
    candidates_token_count: int = 1


@dataclass
class _GemResponse:
    candidates: list = field(default_factory=list)
    usage_metadata: Optional[_GemUsage] = field(default_factory=_GemUsage)


class _FakeGemini:
    def __init__(self):
        self.calls: list[dict] = []
        self.next = _GemResponse(
            candidates=[_GemCandidate(_GemContent([_GemPart(text="hi")]))]
        )

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.next


def _gem_set_text(fake, text):
    fake.next = _GemResponse(
        candidates=[_GemCandidate(_GemContent([_GemPart(text=text)]))]
    )


def _gem_set_tool(fake, name, args):
    fake.next = _GemResponse(
        candidates=[_GemCandidate(
            _GemContent([_GemPart(function_call=_GemFn(name=name, args=args))])
        )]
    )


# --- the conformance cases ---------------------------------------------------


@dataclass
class Case:
    id: str
    make: Callable[[], tuple]          # -> (brain, fake)
    set_text: Callable                 # (fake, text)
    set_tool: Callable                 # (fake, name, args)
    calls: Callable                    # fake -> list[dict] of outgoing calls


CASES = [
    Case("gpt", lambda: (lambda f: (GPTBrain(client=f), f))(_FakeOpenAI()),
         _oai_set_text, _oai_set_tool, lambda f: f.calls),
    Case("universal", lambda: (lambda f: (UniversalBrain(client=f), f))(_FakeOpenAI()),
         _oai_set_text, _oai_set_tool, lambda f: f.calls),
    Case("claude", lambda: (lambda f: (ClaudeBrain(client=f), f))(_FakeAnthropic()),
         _claude_set_text, _claude_set_tool, lambda f: f.calls),
    Case("gemini", lambda: (lambda f: (GeminiBrain(client=f), f))(_FakeGemini()),
         _gem_set_text, _gem_set_tool, lambda f: f.calls),
]

_IDS = [c.id for c in CASES]


@pytest.fixture(params=CASES, ids=_IDS)
def case(request):
    return request.param


def test_satisfies_the_brain_protocol(case):
    brain, _ = case.make()
    assert isinstance(brain, Brain)
    assert isinstance(brain.name, str) and brain.name


def test_text_response_round_trips(case):
    brain, fake = case.make()
    case.set_text(fake, "the answer")
    resp = brain.think("hi")
    assert resp.content == "the answer"
    assert not resp.tool_calls
    assert resp.wants_tools is False


def test_tool_call_is_parsed_into_toolcall(case):
    brain, fake = case.make()
    case.set_tool(fake, "sample_tool", {"city": "Tokyo"})
    resp = brain.think("go", tools=[sample_tool])
    assert resp.wants_tools is True
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "sample_tool"
    assert resp.tool_calls[0].arguments == {"city": "Tokyo"}


def test_tools_are_forwarded_to_the_provider(case):
    brain, fake = case.make()
    brain.think("go", tools=[sample_tool])
    assert "tools" in case.calls(fake)[-1]


def test_empty_tools_are_not_forwarded(case):
    brain, fake = case.make()
    brain.think("go", tools=[])
    assert "tools" not in case.calls(fake)[-1]
