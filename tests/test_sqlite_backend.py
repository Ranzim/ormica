"""Tests for SqliteBackend — single-file SQLite persistence."""
from pathlib import Path

import pytest

from ormica.mycelium import Backend, Entry, Mycelium, SqliteBackend
from ormica.stigma import Stigma


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# --- Backend protocol ---------------------------------------------------------


def test_satisfies_backend_protocol(tmp_path: Path):
    backend = SqliteBackend(tmp_path / "mem.db")
    assert isinstance(backend, Backend)


def test_brand_new_file_starts_empty(tmp_path: Path):
    backend = SqliteBackend(tmp_path / "new.db")
    assert len(backend) == 0
    assert backend.get("anything") is None


def test_parent_directory_created(tmp_path: Path):
    path = tmp_path / "deep" / "nested" / "mem.db"
    backend = SqliteBackend(path)
    backend.set(Entry(key="x", value=1))
    assert path.exists()


# --- Persistence roundtrip ----------------------------------------------------


def test_writes_and_reloads(tmp_path: Path):
    path = tmp_path / "mem.db"
    b = SqliteBackend(path)
    b.set(Entry(key="x", value="hello", author="node-a"))
    b.close()

    fresh = SqliteBackend(path)
    assert "x" in fresh
    entry = fresh.get("x")
    assert entry.value == "hello"
    assert entry.author == "node-a"


def test_delete_persists(tmp_path: Path):
    path = tmp_path / "mem.db"
    b = SqliteBackend(path)
    b.set(Entry(key="x", value=1))
    b.set(Entry(key="y", value=2))
    b.delete("x")
    b.close()

    fresh = SqliteBackend(path)
    assert "x" not in fresh
    assert "y" in fresh


def test_delete_missing_returns_false(tmp_path: Path):
    b = SqliteBackend(tmp_path / "mem.db")
    assert b.delete("nope") is False


def test_meta_and_complex_values_preserved(tmp_path: Path):
    path = tmp_path / "mem.db"
    b = SqliteBackend(path)
    b.set(
        Entry(
            key="record",
            value={"name": "acme", "scores": [1, 2, 3], "active": True},
            meta={"trail": 0.5, "tags": ["a", "b"]},
        )
    )
    b.close()

    fresh = SqliteBackend(path)
    entry = fresh.get("record")
    assert entry.value == {"name": "acme", "scores": [1, 2, 3], "active": True}
    assert entry.meta == {"trail": 0.5, "tags": ["a", "b"]}


def test_upsert_overwrites_existing_key(tmp_path: Path):
    b = SqliteBackend(tmp_path / "mem.db")
    b.set(Entry(key="x", value="first"))
    b.set(Entry(key="x", value="second"))
    assert b.get("x").value == "second"
    assert len(b) == 1


# --- Mycelium integration -----------------------------------------------------


def test_mycelium_through_sqlite_survives_restart(tmp_path: Path):
    path = tmp_path / "mem.db"

    mem = Mycelium(backend=SqliteBackend(path))
    mem.write("policy", "no overtime", author="founder")
    mem.write("rule", "ship weekly", author="founder")
    mem.backend.close()

    mem2 = Mycelium(backend=SqliteBackend(path))
    assert mem2.get("policy") == "no overtime"
    assert mem2.read("rule").author == "founder"


def test_ttl_persists_and_still_expires(tmp_path: Path):
    path = tmp_path / "mem.db"
    clock = FakeClock()
    mem = Mycelium(backend=SqliteBackend(path), clock=clock)
    mem.write("trail", 1.0, ttl=100)
    mem.backend.close()

    later = FakeClock(start=clock.now + 200)
    mem2 = Mycelium(backend=SqliteBackend(path), clock=later)
    assert mem2.read("trail") is None


def test_stigma_signals_persist_across_sessions(tmp_path: Path):
    path = tmp_path / "mem.db"
    clock = FakeClock()

    mem = Mycelium(backend=SqliteBackend(path), clock=clock)
    stig = Stigma(mem)
    stig.emit("trail", strength=2.0, by="ant-1")
    stig.reinforce("trail", amount=1.0, by="ant-2")
    mem.backend.close()

    mem2 = Mycelium(backend=SqliteBackend(path), clock=clock)
    stig2 = Stigma(mem2)
    sensed = stig2.sense("trail")
    assert sensed is not None
    assert sensed.strength == pytest.approx(3.0)
    assert sensed.sources == {"ant-1", "ant-2"}


# --- Ormica facade integration ------------------------------------------------


def test_ormica_memory_db_auto_builds_sqlite(tmp_path: Path):
    from ormica import Ormica

    path = tmp_path / "mem.db"
    org = Ormica("Acme", memory_db=str(path))
    org.write("k", "v")
    org.memory.backend.close()

    org2 = Ormica("Acme", memory_db=str(path))
    assert org2.remember("k") == "v"


def test_memory_db_wins_over_memory_path_when_both_given(tmp_path: Path):
    from ormica import Ormica
    from ormica.mycelium import SqliteBackend as Sb

    db_path = tmp_path / "primary.db"
    file_path = tmp_path / "ignored.json"
    org = Ormica("Acme", memory_db=str(db_path), memory_path=str(file_path))
    assert isinstance(org.memory.backend, Sb)
    assert db_path.exists()
    assert not file_path.exists()


# --- Context manager / close -------------------------------------------------


def test_context_manager_closes_connection(tmp_path: Path):
    path = tmp_path / "mem.db"
    with SqliteBackend(path) as b:
        b.set(Entry(key="x", value=1))
    # Re-open in a fresh handle to prove the write committed.
    fresh = SqliteBackend(path)
    assert fresh.get("x").value == 1
