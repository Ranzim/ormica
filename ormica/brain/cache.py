"""CachingBrain — memoize identical LLM calls to save time and money.

Colonies repeat themselves: the Forest asks N trees the same question, delegation
re-derives shared context, a resumed run re-issues finished prompts. Wrapping any
brain in `CachingBrain` returns the stored answer for a prompt it has already
seen — no second API call, no second bill.

    from ormica.brain import CachingBrain, GeminiBrain
    brain = CachingBrain(GeminiBrain())
    org.run(brain=brain)
    brain.hits, brain.misses   # observe the savings

Deterministic by design: tool-use turns are **not** cached (they depend on live
tool state), and the cache is keyed on the full prompt + system + model. It's an
in-process LRU; pair with mycelium if you want cross-run persistence.
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any, Optional

from .protocol import Prompt, to_messages
from .tool import Tool
from .types import Response


def _key(prompt: Prompt, system: Optional[str], model: str) -> str:
    parts = [f"model:{model}", f"system:{system or ''}"]
    for m in to_messages(prompt):
        parts.append(f"{getattr(m, 'role', '')}:{getattr(m, 'content', '')}")
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


class CachingBrain:
    """Wrap a brain so identical prompts return the stored :class:`Response`.

    ``maxsize`` bounds the in-process LRU (0 = unbounded). Tool-use turns bypass
    the cache. Exposes ``hits`` / ``misses`` for observability.
    """

    def __init__(self, inner: Any, *, maxsize: int = 1024) -> None:
        self.inner = inner
        self.maxsize = maxsize
        self._cache: "OrderedDict[str, Response]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    @property
    def name(self) -> str:
        return f"caching({getattr(self.inner, 'name', 'brain')})"

    def think(
        self,
        prompt: Prompt,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        tools: Optional[list[Tool]] = None,
    ) -> Response:
        if tools:  # tool turns depend on live state — never cache them
            return self.inner.think(prompt, system=system, max_tokens=max_tokens, tools=tools)

        key = _key(prompt, system, getattr(self.inner, "model", ""))
        cached = self._cache.get(key)
        if cached is not None:
            self.hits += 1
            self._cache.move_to_end(key)   # LRU touch
            return cached

        self.misses += 1
        resp = self.inner.think(prompt, system=system, max_tokens=max_tokens)
        self._cache[key] = resp
        if self.maxsize and len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)   # evict least-recently-used
        return resp

    def clear(self) -> None:
        self._cache.clear()
