"""Tests for semantic memory — the search seam on top of Backend."""
import pytest

from ormica import Agent
from ormica.arbor import Tree
from ormica.brain import MockBrain
from ormica.mycelium import (
    Backend,
    Embedder,
    Entry,
    HashingEmbedder,
    InMemoryBackend,
    InMemorySemanticBackend,
    Match,
    Mycelium,
    SearchableBackend,
    SentenceTransformerEmbedder,
)


# --- embedder -----------------------------------------------------------------


def test_hashing_embedder_is_deterministic():
    emb = HashingEmbedder(dim=64)
    assert emb.embed("shared knowledge across agents") == emb.embed(
        "shared knowledge across agents"
    )
    assert len(emb.embed("anything")) == 64


def test_hashing_embedder_shared_words_score_higher():
    emb = HashingEmbedder(dim=512)
    from ormica.mycelium.semantic import _cosine

    a = emb.embed("chip design and hardware layout")
    b = emb.embed("hardware chip layout verification")  # overlaps a lot
    c = emb.embed("patient diagnosis and medicine dosage")  # no overlap
    assert _cosine(a, b) > _cosine(a, c)


# --- backend conforms to both protocols ---------------------------------------


def test_semantic_backend_is_a_backend_and_searchable():
    backend = InMemorySemanticBackend()
    assert isinstance(backend, Backend)
    assert isinstance(backend, SearchableBackend)
    # A plain Backend is NOT searchable.
    assert not isinstance(InMemoryBackend(), SearchableBackend)


def test_semantic_backend_key_value_still_works():
    backend = InMemorySemanticBackend()
    backend.set(Entry(key="k", value="v"))
    assert backend.get("k").value == "v"
    assert "k" in backend
    assert len(backend) == 1
    assert backend.delete("k") is True
    assert len(backend) == 0


# --- search relevance ---------------------------------------------------------


def _seed(myc: Mycelium) -> None:
    myc.write("note:chip", "RISC-V core layout and timing closure for the chip")
    myc.write("note:med", "patient triage protocol and medication dosage")
    myc.write("note:sec", "buffer overflow exploit in the network daemon")


def test_search_ranks_relevant_entry_first():
    myc = Mycelium(InMemorySemanticBackend())
    _seed(myc)
    results = myc.search("chip timing layout", k=3)
    assert results
    assert isinstance(results[0], Match)
    assert results[0].entry.key == "note:chip"
    assert results[0].score > 0.0


def test_search_respects_k():
    myc = Mycelium(InMemorySemanticBackend())
    _seed(myc)
    assert len(myc.search("layout", k=1)) <= 1


def test_search_filters_expired_entries():
    clock = {"t": 1000.0}
    myc = Mycelium(InMemorySemanticBackend(), clock=lambda: clock["t"])
    myc.write("note:chip", "chip layout timing", ttl=5)
    clock["t"] = 2000.0  # entry now expired
    assert myc.search("chip layout timing", k=5) == []


def test_search_on_non_searchable_backend_raises():
    myc = Mycelium(InMemoryBackend())
    with pytest.raises(TypeError, match="does not support search"):
        myc.search("anything")


def test_backend_search_rejects_bad_k():
    with pytest.raises(ValueError):
        InMemorySemanticBackend().search("q", k=0)


# --- agent + scope integration ------------------------------------------------


def test_agent_recall_relevant():
    myc = Mycelium(InMemorySemanticBackend())
    tree = Tree("HQ")
    writer = tree.spawn(tree.root, "researcher")
    reader = tree.spawn(tree.root, "engineer")

    w = Agent(writer, MockBrain(replies=["x"]), memory=myc)
    w.remember("finding:1", "the flaky test is caused by a race in the cache layer")
    w.remember("finding:2", "quarterly revenue grew on enterprise upsells")

    r = Agent(reader, MockBrain(replies=["x"]), memory=myc)
    hits = r.recall_relevant("why is the test flaky race condition", k=1)
    assert hits and hits[0].entry.value.startswith("the flaky test")


def test_recall_relevant_without_memory_returns_empty():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    agent = Agent(node, MockBrain(replies=["x"]))  # no memory
    assert agent.recall_relevant("anything") == []


# --- real embedder (sentence-transformers, behind the memory extra) -----------


class _FakeSentenceModel:
    """Stand-in for a SentenceTransformer: maps known text to fixed vectors."""

    def __init__(self, vectors: dict, dim: int):
        self._vectors = vectors
        self._dim = dim

    def get_sentence_embedding_dimension(self) -> int:
        return self._dim

    def encode(self, text: str):
        # Default to a zero vector for unknown text.
        return self._vectors.get(text, [0.0] * self._dim)


def test_sentence_transformer_embedder_missing_dep_raises():
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match=r"ormica\[memory\]"):
            SentenceTransformerEmbedder()
    else:  # pragma: no cover - only when the extra is installed
        pytest.skip("sentence-transformers is installed; missing-dep path N/A")


def test_sentence_transformer_embedder_with_injected_model():
    fake = _FakeSentenceModel({"hello world": [0.1, 0.2, 0.3]}, dim=3)
    emb = SentenceTransformerEmbedder(model=fake)
    assert isinstance(emb, Embedder)
    assert emb.dim == 3
    assert emb.embed("hello world") == [0.1, 0.2, 0.3]


def test_real_embedder_captures_meaning_without_shared_words():
    """The lexical HashingEmbedder can't; an injected 'real' model can."""
    # Two phrases with NO shared words but near-identical vectors (synonyms),
    # and an unrelated phrase pointing elsewhere.
    vectors = {
        # the query, embedded directly:
        "web app auth vulnerability": [1.0, 0.0, 0.0],
        # entries are embedded as "<key> <value>" (see _entry_text):
        "sec sql injection in a login form": [0.98, 0.1, 0.0],  # ~same direction
        "hw cache coherence across cpu cores": [0.0, 0.0, 1.0],
    }
    fake = _FakeSentenceModel(vectors, dim=3)
    backend = InMemorySemanticBackend(embedder=SentenceTransformerEmbedder(model=fake))
    myc = Mycelium(backend)
    myc.write("sec", "sql injection in a login form")
    myc.write("hw", "cache coherence across cpu cores")

    top = myc.search("web app auth vulnerability", k=1)
    assert top[0].entry.key == "sec"  # meaning matched despite zero shared words


def test_scope_search_delegates():
    myc = Mycelium(InMemorySemanticBackend())
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "w")
    scope = myc.scope(node)
    scope.write("k", "distributed execution across worker nodes")
    assert scope.search("worker nodes", k=1)[0].entry.key == "k"
