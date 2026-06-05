"""SqliteBackend — single-file SQLite persistence for Mycelium."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterator, Optional, Union

from .entry import Entry


_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    author     TEXT,
    written_at REAL NOT NULL,
    expires_at REAL,
    meta       TEXT NOT NULL
);
"""


class SqliteBackend:
    """A :class:`Backend` that persists entries to a SQLite file.

    Better than :class:`FileBackend` for high write volumes: writes are
    O(1) row-level operations rather than O(n) full-file rewrites. Uses
    WAL journal mode so reads do not block on a writer.

    Values must be JSON-serializable. Single-process recommended; the
    file lock is held by SQLite itself.
    """

    def __init__(self, path: Union[Path, str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # ``check_same_thread=False`` so a Mycelium handed to an async runner
        # can be touched from any task. We don't keep a transaction open
        # between calls, so SQLite-level locking is the only concern.
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SqliteBackend":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # --- Backend protocol ---

    def get(self, key: str) -> Optional[Entry]:
        row = self._conn.execute(
            "SELECT key, value, author, written_at, expires_at, meta "
            "FROM entries WHERE key = ?",
            (key,),
        ).fetchone()
        return _row_to_entry(row) if row is not None else None

    def set(self, entry: Entry) -> None:
        self._conn.execute(
            """
            INSERT INTO entries(key, value, author, written_at, expires_at, meta)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value      = excluded.value,
              author     = excluded.author,
              written_at = excluded.written_at,
              expires_at = excluded.expires_at,
              meta       = excluded.meta
            """,
            (
                entry.key,
                json.dumps(entry.value),
                entry.author,
                entry.written_at,
                entry.expires_at,
                json.dumps(entry.meta),
            ),
        )
        self._conn.commit()

    def delete(self, key: str) -> bool:
        cursor = self._conn.execute("DELETE FROM entries WHERE key = ?", (key,))
        self._conn.commit()
        return cursor.rowcount > 0

    def items(self) -> Iterator[Entry]:
        rows = self._conn.execute(
            "SELECT key, value, author, written_at, expires_at, meta FROM entries"
        ).fetchall()
        return iter([_row_to_entry(row) for row in rows])

    def __contains__(self, key: str) -> bool:
        return (
            self._conn.execute(
                "SELECT 1 FROM entries WHERE key = ? LIMIT 1", (key,)
            ).fetchone()
            is not None
        )

    def __len__(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]


def _row_to_entry(row: tuple) -> Entry:
    key, value_json, author, written_at, expires_at, meta_json = row
    return Entry(
        key=key,
        value=json.loads(value_json),
        author=author,
        written_at=written_at,
        expires_at=expires_at,
        meta=json.loads(meta_json),
    )
