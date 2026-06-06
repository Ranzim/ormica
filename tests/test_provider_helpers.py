"""Tests for the provider convenience constructors in ormica.brain.providers."""
from ormica.brain import (
    deepseek_brain,
    groq_brain,
    ollama_brain,
    openrouter_brain,
    together_brain,
)
from ormica.brain.universal import UniversalBrain


# All tests use a sentinel client object so no OpenAI SDK import is needed.
class _FakeClient:
    pass


def test_ollama_brain_points_at_localhost():
    brain = ollama_brain(client=_FakeClient())
    assert isinstance(brain, UniversalBrain)
    assert brain.base_url == "http://localhost:11434/v1"
    assert brain.model == "llama3.2"


def test_ollama_brain_accepts_custom_host():
    brain = ollama_brain(
        host="http://192.168.1.10:11434/",  # trailing slash should be stripped
        model="qwen2.5",
        client=_FakeClient(),
    )
    assert brain.base_url == "http://192.168.1.10:11434/v1"
    assert brain.model == "qwen2.5"


def test_openrouter_brain_points_at_openrouter():
    brain = openrouter_brain(
        model="anthropic/claude-opus-4-7",
        api_key="sk-test",
        client=_FakeClient(),
    )
    assert brain.base_url == "https://openrouter.ai/api/v1"
    assert brain.model == "anthropic/claude-opus-4-7"


def test_groq_brain_defaults_to_llama_70b():
    brain = groq_brain(api_key="gsk-test", client=_FakeClient())
    assert brain.base_url == "https://api.groq.com/openai/v1"
    assert brain.model == "llama-3.3-70b-versatile"


def test_together_brain_defaults_to_llama_70b_turbo():
    brain = together_brain(api_key="t-test", client=_FakeClient())
    assert brain.base_url == "https://api.together.xyz/v1"
    assert brain.model == "meta-llama/Llama-3.3-70B-Instruct-Turbo"


def test_deepseek_brain_defaults_to_deepseek_chat():
    brain = deepseek_brain(api_key="dk-test", client=_FakeClient())
    assert brain.base_url == "https://api.deepseek.com/v1"
    assert brain.model == "deepseek-chat"


def test_async_helpers_return_async_universal_brain():
    from ormica.brain import async_groq_brain, async_ollama_brain
    from ormica.brain.universal import AsyncUniversalBrain

    a = async_ollama_brain(client=_FakeClient())
    b = async_groq_brain(client=_FakeClient(), api_key="x")
    assert isinstance(a, AsyncUniversalBrain)
    assert isinstance(b, AsyncUniversalBrain)
    assert a.base_url == "http://localhost:11434/v1"
    assert b.base_url == "https://api.groq.com/openai/v1"


def test_lazy_exports_via_brain_namespace():
    from ormica import brain as brain_mod

    for name in (
        "ollama_brain", "openrouter_brain", "groq_brain",
        "together_brain", "deepseek_brain",
        "async_ollama_brain", "async_openrouter_brain", "async_groq_brain",
        "async_together_brain", "async_deepseek_brain",
    ):
        assert callable(getattr(brain_mod, name))
