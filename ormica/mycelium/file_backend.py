"""FileBackend — JSON-on-disk persistence for Mycelium."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator, Optional, Union

from .entry import Entry

SCHEMA_VERSION = 1


class FileBackend:
    """A :class:`Backend` that persists entries as a JSON file.

    Entries are loaded into memory on construction and flushed to disk on
    every ``set``/``delete``. Flushes are crash-safe (write-to-``.tmp`` +
    atomic rename). Single-process only — no file locking is performed.

    Values must be JSON-serializable: dicts, lists, strings, numbers, bools,
    and ``None``. Custom types should be encoded by the caller before write.
    """

    def __init__(self, path: Union[Path, str]) -> None:
        self.path = Path(path)
        self._store: dict[str, Entry] = {}
        if self.path.exists() and self.path.stat().st_size > 0:
            self._load()

    # --- persistence ---

    def _load(self) -> None:
        data = json.loads(self.path.read_text())
        version = data.get("__schema_version", 1)
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"FileBackend schema version {version} is unsupported "
                f"(this code reads version {SCHEMA_VERSION})"
            )
        for key, raw in data.get("entries", {}).items():
            self._store[key] = _entry_from_dict(raw)

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "__schema_version": SCHEMA_VERSION,
            "entries": {key: _entry_to_dict(e) for key, e in self._store.items()},
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        os.replace(tmp, self.path)

    # --- Backend protocol ---

    def get(self, key: str) -> Optional[Entry]:
        return self._store.get(key)

    def set(self, entry: Entry) -> None:
        self._store[entry.key] = entry
        self._flush()

    def delete(self, key: str) -> bool:
        if key not in self._store:
            return False
        del self._store[key]
        self._flush()
        return True

    def items(self) -> Iterator[Entry]:
        return iter(list(self._store.values()))

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __len__(self) -> int:
        return len(self._store)


def _entry_to_dict(entry: Entry) -> dict:
    return {
        "key": entry.key,
        "value": entry.value,
        "author": entry.author,
        "written_at": entry.written_at,
        "expires_at": entry.expires_at,
        "meta": entry.meta,
    }


def _entry_from_dict(raw: dict) -> Entry:
    return Entry(
        key=raw["key"],
        value=raw["value"],
        author=raw.get("author"),
        written_at=raw.get("written_at", 0.0),
        expires_at=raw.get("expires_at"),
        meta=raw.get("meta") or {},
    )
