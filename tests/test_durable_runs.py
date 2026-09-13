"""Tests for durable, resumable runs — checkpointing + Ormica.resume."""
import pytest

from ormica import Ormica, Task
from ormica.brain import MockBrain
from ormica.mycelium import InMemoryBackend, Mycelium, SqliteBackend


def _persist(mem: Mycelium, tid: str, status: str, *, desc: str = "x") -> None:
    """Write a tasks/{id} record directly, simulating a prior (partial) run."""
    mem.write(
        f"tasks/{tid}",
        {
            "id": tid,
            "description": desc,
            "target": "",
            "priority": "normal",
            "status": status,
            "result": None,
            "error": None,
            "created_at": 0.0,
        },
    )


# --- Task record round-trip ---------------------------------------------------


def test_task_from_record_round_trip():
    t = Task(description="d", target="sales", priority="high", status="done")
    rebuilt = Task.from_record(
        {
            "id": t.id,
            "description": "d",
            "target": "sales",
            "priority": "high",
            "status": "done",
            "result": "r",
            "error": None,
            "created_at": t.created_at,
        }
    )
    assert rebuilt.id == t.id
    assert rebuilt.status == "done"
    assert rebuilt.result == "r"


# --- checkpointing ------------------------------------------------------------


def test_run_persists_task_records():
    mem = Mycelium(InMemoryBackend())
    org = Ormica("Acme", memory=mem)
    org.task("do A")
    org.run(brain=MockBrain(replies=["ok"]))
    records = [e for e in mem.all() if e.key.startswith("tasks/")]
    assert len(records) == 1
    assert records[0].value["status"] == "done"


def test_pending_tasks_checkpointed_before_they_run():
    # A crash after the first task must leave the second as a durable 'pending'.
    mem = Mycelium(InMemoryBackend())
    org = Ormica("Acme", memory=mem)
    org.task("A")
    org.task("B")

    seen = {"n": 0}

    def boom(_task):
        seen["n"] += 1
        if seen["n"] == 1:
            raise RuntimeError("crash right after the first task")

    with pytest.raises(RuntimeError):
        org.run(brain=MockBrain(replies=["r"]), on_task_done=boom)

    # Fresh org over the same store = a restart.
    restarted = Ormica("Acme", memory=mem)
    statuses = sorted(t.status for t in restarted.load_tasks())
    assert statuses == ["done", "pending"]  # A done, B still pending


# --- resume -------------------------------------------------------------------


def test_resume_skips_done_runs_pending():
    mem = Mycelium(InMemoryBackend())
    _persist(mem, "t1", "done")
    _persist(mem, "t2", "pending")
    org = Ormica("Acme", memory=mem)
    brain = MockBrain(replies=["done"])
    result = org.resume(brain=brain)
    assert result.processed == 1  # only the pending task
    assert len(brain.calls) == 1  # the done task was not re-run


def test_resume_reruns_interrupted_running_task():
    mem = Mycelium(InMemoryBackend())
    _persist(mem, "t1", "running")  # interrupted mid-flight
    org = Ormica("Acme", memory=mem)
    result = org.resume(brain=MockBrain(replies=["ok"]))
    assert result.processed == 1
    assert org.load_tasks()[0].status == "done"


def test_resume_skips_failed_unless_retry():
    mem = Mycelium(InMemoryBackend())
    _persist(mem, "t1", "failed")
    org = Ormica("Acme", memory=mem)

    assert org.resume(brain=MockBrain(replies=["x"])).processed == 0  # skipped
    assert org.resume(brain=MockBrain(replies=["x"]), retry_failed=True).processed == 1


def test_load_tasks_orders_by_created_at():
    mem = Mycelium(InMemoryBackend())
    mem.write("tasks/b", {"id": "b", "description": "B", "status": "pending", "created_at": 200.0})
    mem.write("tasks/a", {"id": "a", "description": "A", "status": "pending", "created_at": 100.0})
    org = Ormica("Acme", memory=mem)
    assert [t.id for t in org.load_tasks()] == ["a", "b"]


# --- cross-instance durability (a real restart) -------------------------------


def test_resume_after_completed_run_reruns_nothing():
    mem = Mycelium(InMemoryBackend())
    org1 = Ormica("Acme", memory=mem)
    org1.task("A")
    org1.task("B")
    org1.run(brain=MockBrain(replies=["r"]))

    org2 = Ormica("Acme", memory=mem)
    result = org2.resume(brain=MockBrain(replies=["r"]))
    assert result.processed == 0  # everything was already done
    assert all(t.status == "done" for t in org2.load_tasks())


def test_durability_across_sqlite_backed_restart(tmp_path):
    db = str(tmp_path / "colony.db")
    org1 = Ormica("Acme", memory=Mycelium(SqliteBackend(db)))
    org1.task("A")
    org1.task("B")
    org1.run(brain=MockBrain(replies=["r"]))

    # New process would reopen the same file.
    org2 = Ormica("Acme", memory=Mycelium(SqliteBackend(db)))
    loaded = org2.load_tasks()
    assert len(loaded) == 2
    assert all(t.status == "done" for t in loaded)
    assert org2.resume(brain=MockBrain(replies=["r"])).processed == 0
