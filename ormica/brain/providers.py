"""Provider convenience constructors — one-liners over :class:`UniversalBrain`.

Each function returns a configured :class:`UniversalBrain` (or async sibling)
pointed at a popular OpenAI-compatible endpoint. Saves you from remembering
URLs.

Usage::

    from ormica.brain import ollama_brain, openrouter_brain, groq_brain

    org.run(brain=ollama_brain(model="llama3.2"))                   # local
    org.run(brain=openrouter_brain(model="anthropic/claude-opus-4-7"))
    org.run(brain=groq_brain(model="llama-3.3-70b-versatile"))

These helpers are thin — they exist for ergonomics. Anything they do you
could do yourself with :class:`UniversalBrain` directly by passing
``base_url=`` and ``api_key=``.
"""
from __future__ import annotations

from typing import Any, Optional

from .universal import AsyncUniversalBrain, UniversalBrain


# --- Sync helpers ------------------------------------------------------------


def ollama_brain(
    *,
    model: str = "llama3.2",
    host: str = "http://localhost:11434",
    client: Any = None,
) -> UniversalBrain:
    """Local LLM via Ollama. Free, private, no real API key required.

    Install Ollama from https://ollama.ai, then ``ollama pull <model>``.
    """
    return UniversalBrain(
        model=model,
        base_url=f"{host.rstrip('/')}/v1",
        api_key="ollama",  # Ollama ignores the key but the SDK requires one
        client=client,
    )


def openrouter_brain(
    *,
    model: str,
    api_key: Optional[str] = None,
    client: Any = None,
) -> UniversalBrain:
    """OpenRouter — one account, 300+ models.

    Sign up at https://openrouter.ai. API key in ``OPENROUTER_API_KEY``.
    Example models: ``anthropic/claude-opus-4-7``, ``meta-llama/llama-3.3-70b-instruct``.
    """
    return UniversalBrain(
        model=model,
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        client=client,
    )


def groq_brain(
    *,
    model: str = "llama-3.3-70b-versatile",
    api_key: Optional[str] = None,
    client: Any = None,
) -> UniversalBrain:
    """Groq — very fast inference for Llama / Mixtral / Gemma.

    Sign up at https://console.groq.com. API key in ``GROQ_API_KEY``.
    """
    return UniversalBrain(
        model=model,
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
        client=client,
    )


def together_brain(
    *,
    model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    api_key: Optional[str] = None,
    client: Any = None,
) -> UniversalBrain:
    """Together AI — hosted open-source models.

    Sign up at https://together.ai. API key in ``TOGETHER_API_KEY``.
    """
    return UniversalBrain(
        model=model,
        base_url="https://api.together.xyz/v1",
        api_key=api_key,
        client=client,
    )


def deepseek_brain(
    *,
    model: str = "deepseek-chat",
    api_key: Optional[str] = None,
    client: Any = None,
) -> UniversalBrain:
    """DeepSeek — strong reasoning at low cost.

    Sign up at https://platform.deepseek.com. API key in ``DEEPSEEK_API_KEY``.
    """
    return UniversalBrain(
        model=model,
        base_url="https://api.deepseek.com/v1",
        api_key=api_key,
        client=client,
    )


# --- Async siblings ----------------------------------------------------------


def async_ollama_brain(
    *,
    model: str = "llama3.2",
    host: str = "http://localhost:11434",
    client: Any = None,
) -> AsyncUniversalBrain:
    return AsyncUniversalBrain(
        model=model,
        base_url=f"{host.rstrip('/')}/v1",
        api_key="ollama",
        client=client,
    )


def async_openrouter_brain(
    *,
    model: str,
    api_key: Optional[str] = None,
    client: Any = None,
) -> AsyncUniversalBrain:
    return AsyncUniversalBrain(
        model=model,
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        client=client,
    )


def async_groq_brain(
    *,
    model: str = "llama-3.3-70b-versatile",
    api_key: Optional[str] = None,
    client: Any = None,
) -> AsyncUniversalBrain:
    return AsyncUniversalBrain(
        model=model,
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
        client=client,
    )


def async_together_brain(
    *,
    model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    api_key: Optional[str] = None,
    client: Any = None,
) -> AsyncUniversalBrain:
    return AsyncUniversalBrain(
        model=model,
        base_url="https://api.together.xyz/v1",
        api_key=api_key,
        client=client,
    )


def async_deepseek_brain(
    *,
    model: str = "deepseek-chat",
    api_key: Optional[str] = None,
    client: Any = None,
) -> AsyncUniversalBrain:
    return AsyncUniversalBrain(
        model=model,
        base_url="https://api.deepseek.com/v1",
        api_key=api_key,
        client=client,
    )
