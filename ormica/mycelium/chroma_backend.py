"""ChromaBackend — persistent semantic memory on a ChromaDB vector store.

This is the production sibling of :class:`InMemorySemanticBackend`: it
implements the same :class:`~ormica.mycelium.semantic.SearchableBackend`
protocol, but embeddings and entries live in a ChromaDB collection that
persists to disk and scales past what fits in one process's RAM. Because it
satisfies the same protocol, :class:`~ormica.mycelium.Mycelium` and every
agent above it are unchanged — this is a drop-in for the storage seam.

Needs the optional dependency::

    pip install ormica[memory]

Embedding is pluggable:

- Pass an :class:`~ormica.mycelium.semantic.Embedder` and this backend
  computes vectors itself (deterministic, provider-agnostic).
- Pass ``embedder=None`` (default) to let Chroma embed with its own
  configured embedding function.

The ``client`` argument lets you inject a pre-built Chroma client (or a fake,
for tests) instead of opening one from ``path``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, Optional, Union

from .entry import Entry
from .semantic import Embedder, Match, _entry_text

DEFAULT_COLLECTION = "ormica_memory"


class ChromaBackend:
    """A persistent :class:`SearchableBackend` backed by ChromaDB."""

    def __init__(
        self,
        path: Optional[Union[Path, str]] = None,
        *,
        collection: str = DEFAULT_COLLECTION,
        embedder: Optional[Embedder] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            try:
                import chromadb
            except ImportError as exc:
                raise ImportError(
                    "ChromaBackend needs chromadb. "
                    "Install with: pip install ormica[memory]"
                ) from exc
            client = (
                chromadb.PersistentClient(path=str(path))
                if path is not None
                else chromadb.EphemeralClient()
            )
        self._client = client
        self.embedder = embedder
        # Cosine space so a Chroma "distance" maps cleanly to similarity.
        self._col = client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"}
        )

    # --- Entry <-> Chroma record mapping ----------------------------------

    @staticmethod
    def _to_metadata(entry: Entry) -> dict:
        # Chroma metadata values must be scalars, so complex fields are JSON.
        md: dict[str, Any] = {
            "_value": json.dumps(entry.value, default=str),
            "_meta": json.dumps(entry.meta or {}),
            "written_at": entry.written_at,
        }
        if entry.author is not None:
            md["author"] = entry.author
        if entry.expires_at is not None:
            md["expires_at"] = entry.expires_at
        return md

    @staticmethod
    def _from_record(key: str, md: dict) -> Entry:
        return Entry(
            key=key,
            value=json.loads(md["_value"]),
            author=md.get("author"),
            written_at=md.get("written_at", 0.0),
            expires_at=md.get("expires_at"),
            meta=json.loads(md.get("_meta", "{}")),
        )

    # --- Backend protocol -------------------------------------------------

    def get(self, key: str) -> Optional[Entry]:
        res = self._col.get(ids=[key], include=["metadatas"])
        ids = res.get("ids") or []
        if not ids:
            return None
        return self._from_record(ids[0], res["metadatas"][0])

    def set(self, entry: Entry) -> None:
        kwargs: dict[str, Any] = {
            "ids": [entry.key],
            "documents": [_entry_text(entry)],
            "metadatas": [self._to_metadata(entry)],
        }
        if self.embedder is not None:
            kwargs["embeddings"] = [self.embedder.embed(_entry_text(entry))]
        self._col.upsert(**kwargs)

    def delete(self, key: str) -> bool:
        if key not in self:
            return False
        self._col.delete(ids=[key])
        return True

    def items(self) -> Iterator[Entry]:
        res = self._col.get(include=["metadatas"])
        ids = res.get("ids") or []
        return iter(
            [self._from_record(k, md) for k, md in zip(ids, res["metadatas"])]
        )

    def __contains__(self, key: str) -> bool:
        res = self._col.get(ids=[key], include=[])
        return bool(res.get("ids"))

    def __len__(self) -> int:
        return self._col.count()

    # --- SearchableBackend protocol ---------------------------------------

    def search(self, query: str, k: int = 5) -> list[Match]:
        if k < 1:
            raise ValueError("k must be >= 1")
        if self.embedder is not None:
            res = self._col.query(
                query_embeddings=[self.embedder.embed(query)],
                n_results=k,
                include=["metadatas", "distances"],
            )
        else:
            res = self._col.query(
                query_texts=[query],
                n_results=k,
                include=["metadatas", "distances"],
            )
        ids = (res.get("ids") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        # Cosine distance -> similarity in [-1, 1]; higher is more relevant.
        return [
            Match(self._from_record(k_, md), 1.0 - dist)
            for k_, md, dist in zip(ids, metas, dists)
        ]
