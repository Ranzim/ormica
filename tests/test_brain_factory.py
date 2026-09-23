"""Tests for make_brain — the one-call brain factory."""
import pytest

from ormica.brain import Brain, MockBrain, make_brain
from ormica.brain.gpt import GPTBrain
from ormica.brain.universal import UniversalBrain

_ALL_KEYS = [
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "GROQ_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "TOGETHER_API_KEY",
]


@pytest.fixture
def clean_env(monkeypatch):
    for k in _ALL_KEYS:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


# --- explicit specs ---------------------------------------------------------


def test_mock_spec_is_offline_and_usable():
    b = make_brain("mock")
    assert isinstance(b, MockBrain)
    assert isinstance(b, Brain)
    assert "MockBrain" in b.think("anything").content


def test_named_provider_builds_the_right_adapter():
    assert isinstance(make_brain("openai", api_key="x"), GPTBrain)
    assert isinstance(make_brain("gpt", api_key="x"), GPTBrain)          # alias


def test_provider_model_shorthand_sets_the_model():
    b = make_brain("openai:gpt-4o-mini", api_key="x")
    assert isinstance(b, GPTBrain)
    assert b.model == "gpt-4o-mini"


def test_explicit_model_overrides_the_spec_model():
    b = make_brain("openai:gpt-4o", model="gpt-4o-mini", api_key="x")
    assert b.model == "gpt-4o-mini"


def test_openai_compatible_provider_builds_universal():
    b = make_brain("groq:llama-3.3-70b-versatile", api_key="x")
    assert isinstance(b, UniversalBrain)
    assert b.model == "llama-3.3-70b-versatile"


def test_kwargs_pass_through_to_the_adapter():
    sentinel = object()
    b = make_brain("openai", client=sentinel)
    assert b.client is sentinel


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="unknown brain"):
        make_brain("not-a-real-provider")


def test_openrouter_without_model_raises():
    with pytest.raises(ValueError, match="needs a model"):
        make_brain("openrouter", api_key="x")


# --- environment auto-detection ---------------------------------------------


def test_auto_detect_picks_provider_from_env(clean_env):
    clean_env.setenv("OPENAI_API_KEY", "x")
    assert isinstance(make_brain(), GPTBrain)


def test_auto_detect_respects_priority_order(clean_env):
    # groq is lower priority than openai; with both set, openai wins
    clean_env.setenv("GROQ_API_KEY", "x")
    clean_env.setenv("OPENAI_API_KEY", "x")
    assert isinstance(make_brain(), GPTBrain)


def test_no_key_falls_back_to_mock_with_warning(clean_env):
    with pytest.warns(UserWarning, match="no LLM provider API key"):
        b = make_brain()
    assert isinstance(b, MockBrain)
