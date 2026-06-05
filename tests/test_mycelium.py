"""Tests for the mycelium module — shared memory, TTL, scoping, backend."""
import pytest

from ormica.arbor import Tree
from ormica.mycelium import Backend, Entry, InMemoryBackend, Mycelium, Scope


class FakeClock:
    """A controllable monotonic clock for deterministic TTL tests."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_write_then_read_roundtrip():
    m = Mycelium()
    entry = m.write("found_lead", "acme corp", author="node-a")

    assert entry.key == "found_lead"
    assert entry.author == "node-a"

    got = m.read("found_lead")
    assert got is not None
    assert got.value == "acme corp"
    assert got.author == "node-a"
    assert got.expires_at is None


def test_read_missing_key_returns_none_and_get_returns_default():
    m = Mycelium()
    assert m.read("nope") is None
    assert m.get("nope", default=42) == 42


def test_ttl_expires_entries_on_read():
    clock = FakeClock()
    m = Mycelium(clock=clock)
    m.write("trail", 1.0, ttl=10)

    assert m.get("trail") == 1.0
    clock.advance(9)
    assert m.get("trail") == 1.0
    clock.advance(2)  # past expiry
    assert m.read("trail") is None
    assert "trail" not in m


def test_prune_expired_removes_dead_entries():
    clock = FakeClock()
    m = Mycelium(clock=clock)
    m.write("alive", "x", ttl=100)
    m.write("dead", "y", ttl=1)

    clock.advance(5)
    removed = m.prune_expired()
    assert removed == 1
    assert "alive" in m
    assert "dead" not in m


def test_by_author_filters_entries():
    m = Mycelium()
    m.write("a", 1, author="node-a")
    m.write("b", 2, author="node-b")
    m.write("c", 3, author="node-a")

    keys = sorted(e.key for e in m.by_author("node-a"))
    assert keys == ["a", "c"]


def test_delete_removes_entry():
    m = Mycelium()
    m.write("x", 1)
    assert m.delete("x") is True
    assert m.delete("x") is False
    assert "x" not in m


def test_len_counts_only_non_expired():
    clock = FakeClock()
    m = Mycelium(clock=clock)
    m.write("a", 1)
    m.write("b", 2, ttl=1)

    assert len(m) == 2
    clock.advance(5)
    assert len(m) == 1


def test_scope_auto_tags_author_from_node():
    tree = Tree("HQ")
    scout = tree.spawn(tree.root, "scout")
    m = Mycelium()

    view = m.scope(scout)
    assert isinstance(view, Scope)

    view.write("sighting", "tree at coord 4,2")
    entry = m.read("sighting")
    assert entry is not None
    assert entry.author == scout.id

    assert [e.key for e in view.mine()] == ["sighting"]


def test_in_memory_backend_satisfies_protocol_and_works_standalone():
    backend: Backend = InMemoryBackend()
    assert isinstance(backend, Backend)
    assert len(backend) == 0

    backend.set(Entry(key="x", value=1))
    assert "x" in backend
    assert backend.get("x").value == 1
    assert backend.delete("x") is True
    assert backend.delete("x") is False


def test_external_backend_is_used_by_mycelium():
    backend = InMemoryBackend()
    m = Mycelium(backend=backend)
    m.write("k", "v")
    assert "k" in backend
    assert backend.get("k").value == "v"


def test_meta_is_stored_and_copied_not_aliased():
    m = Mycelium()
    meta = {"trail_strength": 0.5}
    entry = m.write("trail", "x", meta=meta)
    meta["trail_strength"] = 9.0  # mutate after write

    got = m.read("trail")
    assert got.meta == {"trail_strength": 0.5}
    assert entry.meta == {"trail_strength": 0.5}
