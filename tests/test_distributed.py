"""Tests for distributed execution — atomic leases + workers draining a queue."""
import threading

import pytest

from ormica import ArtifactType, Ormica, Task
from ormica.brain import MockBrain
from ormica.mycelium import FileBackend, InMemoryBackend, Mycelium, SqliteBackend


# --- the claim primitive: in-memory -------------------------------------------


def test_inmemory_claim_is_exclusive():
    b = InMemoryBackend()
    assert b.claim("t", "w1", ttl=10, now=0) is True
    assert b.claim("t", "w2", ttl=10, now=0) is False  # held by w1
    assert b.claim("t", "w1", ttl=10, now=0) is True   # owner heartbeat refreshes


def test_inmemory_lease_expiry_allows_reclaim():
    b = InMemoryBackend()
    assert b.claim("t", "w1", ttl=10, now=0) is True
    assert b.claim("t", "w2", ttl=10, now=5) is False   # still valid
    assert b.claim("t", "w2", ttl=10, now=11) is True   # expired -> reclaimed


def test_inmemory_release():
    b = InMemoryBackend()
    b.claim("t", "w1", ttl=10, now=0)
    assert b.release("t", "w2") is False   # not the owner
    assert b.release("t", "w1") is True
    assert b.claim("t", "w2", ttl=10, now=0) is True  # free after release


# --- the claim primitive: sqlite, across "processes" (separate connections) ---


def test_sqlite_claim_atomic_across_connections(tmp_path):
    path = tmp_path / "colony.db"
    a = SqliteBackend(path)
    b = SqliteBackend(path)
    try:
        first = a.claim("tasks/x", "wA", ttl=10, now=0)
        second = b.claim("tasks/x", "wB", ttl=10, now=0)
        assert (first, second) == (True, False)  # exactly one owner
        # after A releases, B (a different connection) can take it
        assert a.release("tasks/x", "wA") is True
        assert b.claim("tasks/x", "wB", ttl=10, now=1) is True
    finally:
        a.close()
        b.close()


def test_sqlite_lease_expiry_across_connections(tmp_path):
    path = tmp_path / "colony.db"
    a = SqliteBackend(path)
    b = SqliteBackend(path)
    try:
        assert a.claim("tasks/x", "wA", ttl=10, now=0) is True
        assert b.claim("tasks/x", "wB", ttl=10, now=5) is False
        assert b.claim("tasks/x", "wB", ttl=10, now=11) is True  # A's lease expired
    finally:
        a.close()
        b.close()


# --- worker needs a claimable backend -----------------------------------------


def test_worker_requires_claimable_backend(tmp_path):
    org = Ormica("HQ", memory=Mycelium(backend=FileBackend(tmp_path / "m.json")))
    with pytest.raises(TypeError, match="ClaimableBackend"):
        org.run_worker(brain=MockBrain(replies=["x"]), worker_id="w1")


# --- a single worker drains the queue -----------------------------------------


def test_worker_drains_queue():
    org = Ormica("HQ")
    for i in range(5):
        org.task(f"task-{i}")
    tally = org.run_worker(brain=MockBrain(reply_fn=lambda m: "done"), worker_id="w1")
    assert tally.processed == 5
    assert tally.succeeded == 5
    assert all(t.status == "done" for t in org.load_tasks())


def test_worker_respects_dependencies_and_passes_results():
    org = Ormica("HQ")
    org._tasks = [
        Task(description="compute A", id="a"),
        Task(description="use A", id="b", depends_on=["a"]),
    ]
    captured = {}

    def reply(messages):
        text = messages[-1].content
        if "use A" in text:
            captured["b_prompt"] = text
            return "used it"
        return "A=42"

    org.run_worker(brain=MockBrain(reply_fn=reply), worker_id="w1")
    tasks = {t.id: t for t in org.load_tasks()}
    assert tasks["a"].status == "done" and tasks["b"].status == "done"
    # b ran after a and received a's result
    assert "A=42" in captured["b_prompt"]
    assert "Your task: use A" in captured["b_prompt"]


def test_worker_captures_typed_artifact_across_dependency():
    Estimate = ArtifactType("estimate", {"cost": float, "days": int})
    org = Ormica("HQ")
    org._tasks = [
        Task(description="estimate", id="a", produces=Estimate),
        Task(description="summarize", id="b", depends_on=["a"]),
    ]
    captured = {}

    def reply(messages):
        text = messages[-1].content
        if "summarize" in text:
            captured["b"] = text
            return "ok"
        return '{"cost": 20.0, "days": 4}'

    org.run_worker(brain=MockBrain(reply_fn=reply), worker_id="w1")
    tasks = {t.id: t for t in org.load_tasks()}
    assert tasks["a"].artifact is not None and tasks["a"].artifact.get("days") == 4
    # dependent received the upstream artifact as labeled JSON
    assert "(estimate)" in captured["b"] and '"cost": 20.0' in captured["b"]


# --- two workers cooperate without double execution ---------------------------


def test_two_workers_no_double_execution():
    """Two threads sharing one org drain the queue; each task runs exactly once."""
    org = Ormica("HQ")
    n = 12
    for i in range(n):
        org.task(f"task-{i}")

    runs: dict[str, int] = {}
    lock = threading.Lock()

    def reply(messages):
        desc = messages[-1].content
        with lock:
            runs[desc] = runs.get(desc, 0) + 1
        return "done"

    brain = MockBrain(reply_fn=reply)
    tallies = {}

    def work(wid):
        tallies[wid] = org.run_worker(
            brain=brain, worker_id=wid, idle_rounds=5, poll=0.001
        )

    threads = [threading.Thread(target=work, args=(f"w{i}",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # every task ran exactly once, and all are done
    assert sorted(runs) == sorted(f"task-{i}" for i in range(n))
    assert all(count == 1 for count in runs.values())
    assert all(t.status == "done" for t in org.load_tasks())
    # the two workers together processed all n tasks
    assert sum(t.processed for t in tallies.values()) == n
