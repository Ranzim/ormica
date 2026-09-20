"""Backend — the storage seam behind mycelium."""
from __future__ import annotations

import threading
from typing import Iterator, Optional, Protocol, runtime_checkable

from .entry import Entry


@runtime_checkable
class Backend(Protocol):
    """The storage layer.

    Mycelium calls only these methods. In-memory is the default;
    file / sqlite / vector backends slot in without touching Mycelium.
    """

    def get(self, key: str) -> Optional[Entry]: ...
    def set(self, entry: Entry) -> None: ...
    def delete(self, key: str) -> bool: ...
    def items(self) -> Iterator[Entry]: ...
    def __contains__(self, key: str) -> bool: ...
    def __len__(self) -> int: ...


class InMemoryBackend:
    """A dict-backed store. The default; loses state on process exit."""

    def __init__(self) -> None:
        self._store: dict[str, Entry] = {}
        # key -> (owner, expires_at); guarded by _lock for atomic claim/release
        # across threads (async tasks, thread pools). Cross-process coordination
        # needs SqliteBackend.
        self._leases: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Entry]:
        return self._store.get(key)

    def set(self, entry: Entry) -> None:
        self._store[entry.key] = entry

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def items(self) -> Iterator[Entry]:
        return iter(list(self._store.values()))

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __len__(self) -> int:
        return len(self._store)

    # --- ClaimableBackend (in-process, lock-based) ---

    def claim(self, key: str, owner: str, *, ttl: float, now: float) -> bool:
        with self._lock:
            held = self._leases.get(key)
            if held is not None and held[0] != owner and held[1] > now:
                return False
            self._leases[key] = (owner, now + ttl)
            return True

    def release(self, key: str, owner: str) -> bool:
        with self._lock:
            held = self._leases.get(key)
            if held is not None and held[0] == owner:
                del self._leases[key]
                return True
            return False
