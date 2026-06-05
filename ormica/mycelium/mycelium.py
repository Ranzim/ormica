"""Mycelium — the shared memory layer."""
from __future__ import annotations

from time import time
from typing import Any, Callable, Optional

from ormica.arbor import Node

from .backend import Backend, InMemoryBackend
from .entry import Entry


class Mycelium:
    """Shared memory linking every agent in the colony.

    Key-value with author tagging, write timestamps, and optional TTL.
    Expired entries are silently filtered from reads. Pluggable backends
    handle persistence; the default is in-memory.
    """

    def __init__(
        self,
        backend: Optional[Backend] = None,
        *,
        clock: Callable[[], float] = time,
    ) -> None:
        # ``or`` would discard an empty backend because __len__ makes it falsy.
        self.backend: Backend = backend if backend is not None else InMemoryBackend()
        self._clock = clock

    def now(self) -> float:
        """Current time according to this mycelium's clock."""
        return self._clock()

    def write(
        self,
        key: str,
        value: Any,
        *,
        author: Optional[str] = None,
        ttl: Optional[float] = None,
        meta: Optional[dict] = None,
    ) -> Entry:
        now = self._clock()
        entry = Entry(
            key=key,
            value=value,
            author=author,
            written_at=now,
            expires_at=(now + ttl) if ttl is not None else None,
            meta=dict(meta) if meta else {},
        )
        self.backend.set(entry)
        return entry

    def read(self, key: str) -> Optional[Entry]:
        entry = self.backend.get(key)
        if entry is None or entry.is_expired(self._clock()):
            return None
        return entry

    def get(self, key: str, default: Any = None) -> Any:
        """Shortcut returning the value at ``key`` or ``default``."""
        entry = self.read(key)
        return entry.value if entry is not None else default

    def delete(self, key: str) -> bool:
        return self.backend.delete(key)

    def all(self) -> list[Entry]:
        now = self._clock()
        return [e for e in self.backend.items() if not e.is_expired(now)]

    def by_author(self, author: str) -> list[Entry]:
        return [e for e in self.all() if e.author == author]

    def prune_expired(self) -> int:
        now = self._clock()
        expired = [e.key for e in self.backend.items() if e.is_expired(now)]
        for key in expired:
            self.backend.delete(key)
        return len(expired)

    def scope(self, node: Node) -> "Scope":
        return Scope(self, author=node.id)

    def __contains__(self, key: str) -> bool:
        entry = self.backend.get(key)
        return entry is not None and not entry.is_expired(self._clock())

    def __len__(self) -> int:
        return len(self.all())


class Scope:
    """A per-author view of mycelium. Writes auto-apply the author tag."""

    def __init__(self, mycelium: Mycelium, author: str) -> None:
        self.mycelium = mycelium
        self.author = author

    def write(
        self,
        key: str,
        value: Any,
        *,
        ttl: Optional[float] = None,
        meta: Optional[dict] = None,
    ) -> Entry:
        return self.mycelium.write(key, value, author=self.author, ttl=ttl, meta=meta)

    def read(self, key: str) -> Optional[Entry]:
        return self.mycelium.read(key)

    def get(self, key: str, default: Any = None) -> Any:
        return self.mycelium.get(key, default)

    def mine(self) -> list[Entry]:
        return self.mycelium.by_author(self.author)
