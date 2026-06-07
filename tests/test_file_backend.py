"""Tests for mycelium's FileBackend — JSON-on-disk persistence."""
import json
from pathlib import Path

import pytest

from ormica.mycelium import Backend, Entry, FileBackend, Mycelium
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
    backend = FileBackend(tmp_path / "mem.json")
    assert isinstance(backend, Backend)


def test_missing_file_starts_empty(tmp_path: Path):
    backend = FileBackend(tmp_path / "does_not_exist.json")
    assert len(backend) == 0
    assert backend.get("anything") is None


def test_empty_file_treated_as_empty_store(tmp_path: Path):
    path = tmp_path / "mem.json"
    path.write_text("")
    backend = FileBackend(path)
    assert len(backend) == 0


def test_parent_directories_created_on_flush(tmp_path: Path):
    path = tmp_path / "nested" / "deep" / "mem.json"
    backend = FileBackend(path)
    backend.set(Entry(key="x", value=1))
    assert path.exists()


# --- Persistence roundtrip ----------------------------------------------------


def test_writes_and_reloads_in_a_fresh_instance(tmp_path: Path):
    path = tmp_path / "mem.json"
    backend = FileBackend(path)
    backend.set(Entry(key="x", value="hello", author="node-a"))

    fresh = FileBackend(path)
    assert "x" in fresh
    entry = fresh.get("x")
    assert entry.value == "hello"
    assert entry.author == "node-a"


def test_delete_persists_to_disk(tmp_path: Path):
    path = tmp_path / "mem.json"
    backend = FileBackend(path)
    backend.set(Entry(key="x", value=1))
    backend.set(Entry(key="y", value=2))
    backend.delete("x")

    fresh = FileBackend(path)
    assert "x" not in fresh
    assert "y" in fresh


def test_delete_missing_key_returns_false_and_does_not_rewrite(tmp_path: Path):
    path = tmp_path / "mem.json"
    backend = FileBackend(path)
    assert backend.delete("nope") is False
    assert not path.exists()  # nothing to flush


def test_meta_preserved_through_persistence(tmp_path: Path):
    path = tmp_path / "mem.json"
    backend = FileBackend(path)
    backend.set(Entry(key="x", value=1, meta={"trail": 0.5, "tags": ["a", "b"]}))

    fresh = FileBackend(path)
    assert fresh.get("x").meta == {"trail": 0.5, "tags": ["a", "b"]}


def test_complex_value_preserved(tmp_path: Path):
    path = tmp_path / "mem.json"
    backend = FileBackend(path)
    backend.set(
        Entry(
            key="record",
            value={
                "name": "acme",
                "scores": [1, 2, 3],
                "active": True,
                "notes": None,
            },
        )
    )

    fresh = FileBackend(path)
    assert fresh.get("record").value == {
        "name": "acme",
        "scores": [1, 2, 3],
        "active": True,
        "notes": None,
    }


# --- On-disk format ----------------------------------------------------------


def test_file_contains_schema_version_marker(tmp_path: Path):
    path = tmp_path / "mem.json"
    backend = FileBackend(path)
    backend.set(Entry(key="x", value=1))

    data = json.loads(path.read_text())
    assert data["__schema_version"] == 1
    assert "x" in data["entries"]


def test_unknown_schema_version_raises(tmp_path: Path):
    path = tmp_path / "mem.json"
    path.write_text(json.dumps({"__schema_version": 999, "entries": {}}))
    with pytest.raises(ValueError, match="schema version"):
        FileBackend(path)


def test_atomic_write_leaves_no_tmp_file(tmp_path: Path):
    path = tmp_path / "mem.json"
    backend = FileBackend(path)
    backend.set(Entry(key="x", value=1))
    tmp_file = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_file.exists()


# --- Integration with Mycelium and Stigma -------------------------------------


def test_mycelium_through_file_backend_survives_restart(tmp_path: Path):
    path = tmp_path / "mem.json"

    mem = Mycelium(backend=FileBackend(path))
    mem.write("policy", "no overtime", author="founder")
    mem.write("rule", "ship weekly", author="founder")

    mem2 = Mycelium(backend=FileBackend(path))
    assert mem2.get("policy") == "no overtime"
    assert mem2.read("rule").author == "founder"


def test_ttl_survives_reload_and_still_expires(tmp_path: Path):
    path = tmp_path / "mem.json"
    clock = FakeClock()
    mem = Mycelium(backend=FileBackend(path), clock=clock)
    mem.write("trail", 1.0, ttl=100)

    later_clock = FakeClock(start=clock.now + 200)  # 200s in the future
    mem2 = Mycelium(backend=FileBackend(path), clock=later_clock)
    assert mem2.read("trail") is None  # expired even after reload


def test_stigma_signals_persist_across_sessions(tmp_path: Path):
    path = tmp_path / "mem.json"
    clock = FakeClock()

    mem = Mycelium(backend=FileBackend(path), clock=clock)
    stig = Stigma(mem)
    stig.emit("trail", strength=2.0, by="ant-1")
    stig.reinforce("trail", amount=1.0, by="ant-2")

    # Restart on the same clock — no decay between sessions.
    mem2 = Mycelium(backend=FileBackend(path), clock=clock)
    stig2 = Stigma(mem2)
    sensed = stig2.sense("trail")
    assert sensed is not None
    assert sensed.strength == pytest.approx(3.0)
    assert sensed.sources == {"ant-1", "ant-2"}


# --- Ormica facade integration ------------------------------------------------


def test_ormica_memory_path_auto_builds_file_backend(tmp_path: Path):
    from ormica import Ormica

    path = tmp_path / "mem.json"
    org = Ormica("Acme", memory_path=str(path))
    org.write("k", "v")

    # New Ormica instance pointed at the same file sees the prior write.
    org2 = Ormica("Acme", memory_path=str(path))
    assert org2.remember("k") == "v"


def test_ormica_explicit_memory_wins_over_memory_path(tmp_path: Path):
    from ormica import Ormica
    from ormica.mycelium import Mycelium

    explicit = Mycelium()
    org = Ormica("Acme", memory=explicit, memory_path=str(tmp_path / "ignored.json"))
    assert org.memory is explicit
    assert not (tmp_path / "ignored.json").exists()


def test_memory_path_alone_uses_file_backend(tmp_path: Path):
    from ormica import Ormica

    file_path = tmp_path / "x.json"
    org = Ormica("Acme", memory_path=str(file_path))
    assert isinstance(org.memory.backend, FileBackend)
