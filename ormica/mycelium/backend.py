"""Backend — the storage seam behind mycelium."""
from __future__ import annotations

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
