"""Tests for ChromaBackend — persistent semantic memory.

chromadb itself is not required: a fake client/collection stands in so the
Entry<->record mapping and search wiring are exercised offline. One test
covers the real missing-dependency path.
"""
import pytest

from ormica import Agent
from ormica.arbor import Tree
from ormica.brain import MockBrain
from ormica.mycelium import (
    Backend,
    ChromaBackend,
    Entry,
    HashingEmbedder,
    Match,
    Mycelium,
    SearchableBackend,
)
from ormica.mycelium.semantic import _cosine


class _FakeCollection:
    """A minimal stand-in for a chromadb collection."""

    def __init__(self, embed_fn=None):
        self._order: list[str] = []
        self._docs: dict[str, str] = {}
        self._meta: dict[str, dict] = {}
        self._emb: dict[str, list] = {}
        self._embed_fn = embed_fn

    def upsert(self, ids, documents=None, metadatas=None, embeddings=None):
        for i, key in enumerate(ids):
            if key not in self._order:
                self._order.append(key)
            if documents:
                self._docs[key] = documents[i]
            if metadatas:
                self._meta[key] = metadatas[i]
            if embeddings is not None:
                self._emb[key] = embeddings[i]
            elif self._embed_fn is not None and documents:
                self._emb[key] = self._embed_fn(documents[i])

    add = upsert

    def get(self, ids=None, include=None):
        keys = ids if ids is not None else list(self._order)
        present = [k for k in keys if k in self._order]
        return {"ids": present, "metadatas": [self._meta.get(k) for k in present]}

    def delete(self, ids):
        for k in ids:
            if k in self._order:
                self._order.remove(k)
                self._docs.pop(k, None)
                self._meta.pop(k, None)
                self._emb.pop(k, None)

    def count(self):
        return len(self._order)

    def query(self, query_embeddings=None, query_texts=None, n_results=10, include=None):
        q = query_embeddings[0] if query_embeddings is not None else self._embed_fn(
            query_texts[0]
        )
        scored = [(k, _cosine(q, self._emb[k])) for k in self._order if k in self._emb]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:n_results]
        return {
            "ids": [[k for k, _ in top]],
            "metadatas": [[self._meta[k] for k, _ in top]],
            "distances": [[1.0 - s for _, s in top]],
        }


class _FakeClient:
    def __init__(self, embed_fn=None):
        self._cols: dict = {}
        self._embed_fn = embed_fn

    def get_or_create_collection(self, name, metadata=None):
        return self._cols.setdefault(name, _FakeCollection(self._embed_fn))


def _backend(embedder=None, embed_fn=None) -> ChromaBackend:
    return ChromaBackend(client=_FakeClient(embed_fn), embedder=embedder)


# --- dependency + protocol ----------------------------------------------------


def test_missing_dep_raises():
    try:
        import chromadb  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match=r"ormica\[memory\]"):
            ChromaBackend(path="/tmp/whatever")
    else:  # pragma: no cover - only when the extra is installed
        pytest.skip("chromadb is installed; missing-dep path N/A")


def test_conforms_to_backend_and_searchable():
    b = _backend(embedder=HashingEmbedder())
    assert isinstance(b, Backend)
    assert isinstance(b, SearchableBackend)


# --- key-value round trip -----------------------------------------------------


def test_set_get_contains_len_delete():
    b = _backend(embedder=HashingEmbedder())
    b.set(Entry(key="k", value="hello"))
    assert "k" in b
    assert len(b) == 1
    assert b.get("k").value == "hello"
    assert b.get("missing") is None
    assert b.delete("k") is True
    assert b.delete("k") is False
    assert len(b) == 0


def test_entry_fields_round_trip():
    b = _backend(embedder=HashingEmbedder())
    b.set(
        Entry(
            key="k",
            value={"nested": [1, 2, 3]},
            author="node-7",
            written_at=123.5,
            expires_at=999.0,
            meta={"tag": "x"},
        )
    )
    e = b.get("k")
    assert e.value == {"nested": [1, 2, 3]}
    assert e.author == "node-7"
    assert e.written_at == 123.5
    assert e.expires_at == 999.0
    assert e.meta == {"tag": "x"}


def test_none_author_and_expiry_round_trip():
    b = _backend(embedder=HashingEmbedder())
    b.set(Entry(key="k", value="v"))  # author None, expires_at None
    e = b.get("k")
    assert e.author is None
    assert e.expires_at is None


def test_items_returns_all():
    b = _backend(embedder=HashingEmbedder())
    b.set(Entry(key="a", value="1"))
    b.set(Entry(key="b", value="2"))
    keys = {e.key for e in b.items()}
    assert keys == {"a", "b"}


# --- search -------------------------------------------------------------------


def test_search_ranks_relevant_first_with_embedder():
    b = _backend(embedder=HashingEmbedder(dim=512))
    b.set(Entry(key="chip", value="RISC-V core layout and timing closure"))
    b.set(Entry(key="med", value="patient triage and medication dosage"))
    results = b.search("chip timing layout", k=2)
    assert results
    assert isinstance(results[0], Match)
    assert results[0].entry.key == "chip"
    assert results[0].score > 0.0


def test_search_text_path_uses_collection_embedding_function():
    # embedder=None -> backend must query by text; the fake collection embeds.
    b = _backend(embedder=None, embed_fn=HashingEmbedder(dim=512).embed)
    b.set(Entry(key="chip", value="hardware chip layout"))
    b.set(Entry(key="sec", value="network exploit payload"))
    results = b.search("chip layout hardware", k=1)
    assert results[0].entry.key == "chip"


def test_search_rejects_bad_k():
    with pytest.raises(ValueError):
        _backend(embedder=HashingEmbedder()).search("q", k=0)


# --- through Mycelium / Agent -------------------------------------------------


def test_mycelium_search_and_expiry_filter():
    clock = {"t": 1000.0}
    myc = Mycelium(_backend(embedder=HashingEmbedder(dim=512)), clock=lambda: clock["t"])
    myc.write("chip", "chip layout timing", ttl=5)
    myc.write("other", "unrelated marketing copy")
    clock["t"] = 2000.0  # chip entry now expired
    hits = myc.search("chip layout timing", k=5)
    assert all(m.entry.key != "chip" for m in hits)


def test_agent_recall_relevant_over_chroma():
    myc = Mycelium(_backend(embedder=HashingEmbedder(dim=512)))
    tree = Tree("HQ")
    writer = tree.spawn(tree.root, "researcher")
    reader = tree.spawn(tree.root, "engineer")
    Agent(writer, MockBrain(replies=["x"]), memory=myc).remember(
        "f1", "the flaky test is a race in the cache layer"
    )
    hits = Agent(reader, MockBrain(replies=["x"]), memory=myc).recall_relevant(
        "flaky test race cache", k=1
    )
    assert hits and hits[0].entry.key == "f1"
