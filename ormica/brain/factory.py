"""``make_brain`` — one call to get a Brain by name or from the environment.

The Brain layer is broad: Claude, OpenAI, Gemini, and every OpenAI-compatible
provider (Groq, DeepSeek, OpenRouter, Together, Ollama) all speak the same
:class:`~ormica.brain.protocol.Brain` protocol, tool calling included. This
helper removes the last friction — remembering which class and base URL to
import — so switching models is a one-liner and never Claude-only.

Examples::

    from ormica.brain import make_brain

    make_brain()                                   # auto-detect from env keys
    make_brain("mock")                             # offline, no key, no cost
    make_brain("groq:llama-3.3-70b-versatile")     # provider:model shorthand
    make_brain("openai", model="gpt-4o-mini")
    make_brain("gemini", api_key="...")

With no argument it picks the first provider whose API key is present in the
environment; if none is set it falls back to the offline :class:`MockBrain`
and warns, so zero-config code still runs.
"""
from __future__ import annotations

import os
import warnings
from typing import Any, Optional

from .protocol import Brain

# Auto-detect order: first env var that is set wins.
_ENV_ORDER: list[tuple[str, str]] = [
    ("ANTHROPIC_API_KEY", "claude"),
    ("OPENAI_API_KEY", "openai"),
    ("GEMINI_API_KEY", "gemini"),
    ("GOOGLE_API_KEY", "gemini"),
    ("GROQ_API_KEY", "groq"),
    ("DEEPSEEK_API_KEY", "deepseek"),
    ("OPENROUTER_API_KEY", "openrouter"),
    ("TOGETHER_API_KEY", "together"),
]

# Friendly aliases -> canonical provider key.
_ALIASES: dict[str, str] = {
    "mock": "mock",
    "claude": "claude", "anthropic": "claude",
    "openai": "openai", "gpt": "openai",
    "gemini": "gemini", "google": "gemini",
    "groq": "groq",
    "deepseek": "deepseek",
    "openrouter": "openrouter",
    "together": "together",
    "ollama": "ollama",
}

_KNOWN = "mock, claude, openai, gemini, groq, deepseek, openrouter, together, ollama"


def make_brain(
    spec: Optional[str] = None,
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> Brain:
    """Return a :class:`Brain` by name, or auto-detect one from the environment.

    ``spec`` may be a provider name (``"groq"``) or ``"provider:model"``
    (``"groq:llama-3.3-70b-versatile"``). ``model`` and ``api_key`` override
    whatever the spec or defaults supply. Extra ``kwargs`` pass straight to
    the adapter (e.g. ``client=`` for tests, ``host=`` for Ollama).
    """
    if spec is None:
        return _from_env(model=model, api_key=api_key, **kwargs)

    if ":" in spec:
        prov, _, spec_model = spec.partition(":")
        model = model or spec_model or None
    else:
        prov = spec

    canonical = _ALIASES.get(prov.strip().lower())
    if canonical is None:
        raise ValueError(f"unknown brain {spec!r}. Known providers: {_KNOWN}")
    return _build(canonical, model=model, api_key=api_key, **kwargs)


def _from_env(**kw: Any) -> Brain:
    for env_var, prov in _ENV_ORDER:
        if os.environ.get(env_var):
            return _build(prov, **kw)
    warnings.warn(
        "make_brain(): no LLM provider API key found in the environment, "
        "falling back to the offline MockBrain. Set one of "
        "ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / GROQ_API_KEY "
        "(and others), or call make_brain('<provider>') explicitly.",
        UserWarning,
        stacklevel=3,
    )
    return _build("mock", **kw)


def _opts(model: Optional[str], api_key: Optional[str], kwargs: dict) -> dict:
    o = dict(kwargs)
    if model is not None:
        o["model"] = model
    if api_key is not None:
        o["api_key"] = api_key
    return o


def _build(prov: str, *, model: Optional[str] = None,
           api_key: Optional[str] = None, **kwargs: Any) -> Brain:
    o = _opts(model, api_key, kwargs)

    if prov == "mock":
        from .mock import MockBrain
        return MockBrain(
            reply_fn=lambda messages: "(offline MockBrain — configure a real "
            "provider for real answers)"
        )
    if prov == "claude":
        from .claude import ClaudeBrain
        return ClaudeBrain(**o)
    if prov == "openai":
        from .gpt import GPTBrain
        return GPTBrain(**o)
    if prov == "gemini":
        from .gemini import GeminiBrain
        return GeminiBrain(**o)

    from . import providers
    builders = {
        "groq": providers.groq_brain,
        "deepseek": providers.deepseek_brain,
        "openrouter": providers.openrouter_brain,
        "together": providers.together_brain,
        "ollama": providers.ollama_brain,
    }
    if prov == "openrouter" and "model" not in o:
        raise ValueError(
            "make_brain('openrouter') needs a model, e.g. "
            "make_brain('openrouter:anthropic/claude-opus-4-7')"
        )
    return builders[prov](**o)
