"""UniversalBrain — one adapter for every OpenAI-compatible LLM endpoint.

Most LLM providers now expose an OpenAI-compatible HTTP API, even when their
native API is something else. ``UniversalBrain`` is a thin wrapper over the
``openai`` SDK with ``base_url`` exposed, so the same class works for:

  - OpenAI (default)
  - Ollama (local — ``http://localhost:11434/v1``)
  - OpenRouter (300+ models — ``https://openrouter.ai/api/v1``)
  - Groq (very fast inference — ``https://api.groq.com/openai/v1``)
  - Together AI, DeepSeek, Mistral La Plateforme, Anyscale, Fireworks,
    vLLM (self-hosted), LM Studio (local desktop), and any other
    OpenAI-compatible endpoint.

Native APIs that are NOT OpenAI-compatible (Anthropic Claude, Google Gemini)
have their own dedicated adapters: :class:`ClaudeBrain`, :class:`GeminiBrain`.

For convenience constructors per provider, see :mod:`ormica.brain.providers`.
"""
from __future__ import annotations

from typing import Any, Optional

from .gpt import _openai_messages, _openai_response_to_internal, _tools_to_openai
from .protocol import Prompt
from .tool import Tool
from .types import Response

DEFAULT_MODEL = "gpt-4o"


class UniversalBrain:
    """A :class:`Brain` adapter for any OpenAI-compatible HTTP endpoint.

    Defaults to OpenAI's hosted API. Override ``base_url`` to point at a
    different provider (Ollama, OpenRouter, Groq, etc.); override
    ``api_key`` to authenticate against that provider.

    Examples::

        from ormica.brain import UniversalBrain

        # Local Ollama (no real key needed; the SDK requires a non-empty string)
        UniversalBrain(base_url="http://localhost:11434/v1",
                       model="llama3.2",
                       api_key="ollama")

        # OpenRouter — one account, 300+ models
        UniversalBrain(base_url="https://openrouter.ai/api/v1",
                       model="anthropic/claude-opus-4-7",
                       api_key=os.environ["OPENROUTER_API_KEY"])

        # Groq (very fast Llama / Mixtral)
        UniversalBrain(base_url="https://api.groq.com/openai/v1",
                       model="llama-3.3-70b-versatile",
                       api_key=os.environ["GROQ_API_KEY"])

    Requires the ``openai`` SDK: ``pip install ormica[openai]``.
    """

    name = "universal"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ImportError(
                    "UniversalBrain needs the openai SDK. "
                    "Install with: pip install ormica[openai]"
                ) from exc
            kwargs: dict[str, Any] = {}
            # The SDK requires a non-empty api_key string; some local providers
            # (Ollama, LM Studio) don't actually authenticate, but the client
            # still needs something to pass along.
            if api_key is not None:
                kwargs["api_key"] = api_key
            if base_url is not None:
                kwargs["base_url"] = base_url
            client = OpenAI(**kwargs)
        self.client = client
        self.model = model
        self.base_url = base_url

    def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tools: Optional[list[Tool]] = None,
    ) -> Response:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": _openai_messages(prompt, system=system),
            "max_tokens": max_tokens,
        }
        openai_tools = _tools_to_openai(tools)
        if openai_tools:
            kwargs["tools"] = openai_tools
        api_response = self.client.chat.completions.create(**kwargs)
        return _openai_response_to_internal(api_response, self.model)


class AsyncUniversalBrain:
    """Async sibling of :class:`UniversalBrain` — uses ``openai.AsyncOpenAI``."""

    name = "async-universal"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise ImportError(
                    "AsyncUniversalBrain needs the openai SDK. "
                    "Install with: pip install ormica[openai]"
                ) from exc
            kwargs: dict[str, Any] = {}
            if api_key is not None:
                kwargs["api_key"] = api_key
            if base_url is not None:
                kwargs["base_url"] = base_url
            client = AsyncOpenAI(**kwargs)
        self.client = client
        self.model = model
        self.base_url = base_url

    async def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tools: Optional[list[Tool]] = None,
    ) -> Response:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": _openai_messages(prompt, system=system),
            "max_tokens": max_tokens,
        }
        openai_tools = _tools_to_openai(tools)
        if openai_tools:
            kwargs["tools"] = openai_tools
        api_response = await self.client.chat.completions.create(**kwargs)
        return _openai_response_to_internal(api_response, self.model)
