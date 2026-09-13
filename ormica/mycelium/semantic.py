"""Semantic memory — the search seam on top of :class:`Backend`.

The base :class:`~ormica.mycelium.backend.Backend` is pure key-value: an
agent must know the exact key to recall something. That's fine for a handful
of agents, but the "live shared brain across every born node" vision needs
*relevance* recall — an agent asks a fuzzy question and gets back the most
related knowledge other agents wrote, without knowing the keys.

This module adds that as a **protocol extension**, not a rewrite:

- :class:`SearchableBackend` — ``Backend`` plus ``search(query, k)``.
- :class:`Embedder` — turns text into a vector; pluggable.
- :class:`HashingEmbedder` — the default: deterministic, zero-dependency,
  offline. It is **lexical** (bag-of-words cosine), not truly semantic —
  good enough to prototype and test the seam. For real semantics, drop in
  an embedder backed by sentence-transformers or an embeddings API, or use
  a vector store (ChromaDB) as the backend. Nothing else changes.
- :class:`InMemorySemanticBackend` — a working ``SearchableBackend`` that
  embeds entries on write and cosine-ranks them on search.

Because ``InMemorySemanticBackend`` also satisfies ``Backend``, a
:class:`~ormica.mycelium.Mycelium` built on it keeps working exactly as
before — ``search`` is purely additive.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Iterator, Optional, Protocol, runtime_checkable

from .backend import Backend
from .entry import Entry

_TOKEN_RE = re.compile(r"[a-z0-9]+")

DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _entry_text(entry: Entry) -> str:
    """The document embedded for an entry: its key plus its stringified value."""
    value = entry.value
    if isinstance(value, str):
        body = value
    else:
        try:
            body = json.dumps(value, default=str)
        except (TypeError, ValueError):
            body = str(value)
    return f"{entry.key} {body}"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass
class Match:
    """A search hit: the matched :class:`Entry` and its similarity score (0–1)."""

    entry: Entry
    score: float


@runtime_checkable
class Embedder(Protocol):
    """Turns text into a fixed-length vector."""

    dim: int

    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Deterministic, dependency-free bag-of-words embedder.

    Each token is hashed into one of ``dim`` buckets; the vector counts token
    occurrences. Similarity is therefore *lexical overlap*, not meaning — two
    texts score high when they share words. It exists so the semantic seam can
    be exercised and tested offline. Swap it for a real embedder for true
    semantics; the interface is identical.
    """

    def __init__(self, dim: int = 256) -> None:
        if dim < 1:
            raise ValueError("dim must be >= 1")
        self.dim = dim

    def _bucket(self, token: str) -> int:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big") % self.dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokenize(text):
            vec[self._bucket(token)] += 1.0
        return vec


class SentenceTransformerEmbedder:
    """Real semantic embedder backed by ``sentence-transformers``.

    Unlike :class:`HashingEmbedder`, this understands *meaning* — "web app
    auth vulnerability" and "SQL injection in a login form" score high even
    with no shared words. Needs the optional dependency::

        pip install ormica[memory]

    ``model`` may be injected (any object with ``encode(text) -> sequence``)
    so tests and custom models can bypass the default download.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBED_MODEL,
        *,
        model: Any = None,
    ) -> None:
        if model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "SentenceTransformerEmbedder needs sentence-transformers. "
                    "Install with: pip install ormica[memory]"
                ) from exc
            model = SentenceTransformer(model_name)
        self._model = model
        get_dim = getattr(model, "get_sentence_embedding_dimension", None)
        self.dim: int = get_dim() if callable(get_dim) else 0

    def embed(self, text: str) -> list[float]:
        vec = [float(x) for x in self._model.encode(text)]
        if not self.dim:
            self.dim = len(vec)
        return vec


@runtime_checkable
class SearchableBackend(Backend, Protocol):
    """A :class:`Backend` that also supports relevance search."""

    def search(self, query: str, k: int = 5) -> list[Match]: ...


class InMemorySemanticBackend:
    """An in-memory :class:`SearchableBackend`.

    Behaves like :class:`~ormica.mycelium.backend.InMemoryBackend` for
    key-value access, and additionally embeds each entry on ``set`` so
    ``search`` can cosine-rank them. State is lost on process exit — this is
    the reference impl for the seam, not a production store. For persistence
    at scale, back the same protocol with a vector database.
    """

    def __init__(self, embedder: Optional[Embedder] = None) -> None:
        self.embedder: Embedder = embedder or HashingEmbedder()
        self._store: dict[str, Entry] = {}
        self._vectors: dict[str, list[float]] = {}

    # --- Backend ----------------------------------------------------------

    def get(self, key: str) -> Optional[Entry]:
        return self._store.get(key)

    def set(self, entry: Entry) -> None:
        self._store[entry.key] = entry
        self._vectors[entry.key] = self.embedder.embed(_entry_text(entry))

    def delete(self, key: str) -> bool:
        self._vectors.pop(key, None)
        return self._store.pop(key, None) is not None

    def items(self) -> Iterator[Entry]:
        return iter(list(self._store.values()))

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __len__(self) -> int:
        return len(self._store)

    # --- SearchableBackend ------------------------------------------------

    def search(self, query: str, k: int = 5) -> list[Match]:
        if k < 1:
            raise ValueError("k must be >= 1")
        q = self.embedder.embed(query)
        scored = [
            Match(entry, _cosine(q, self._vectors[key]))
            for key, entry in self._store.items()
        ]
        scored = [m for m in scored if m.score > 0.0]
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:k]
