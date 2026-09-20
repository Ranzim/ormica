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


def test_owner_reclaim_refreshes_lease():
    # the heartbeat relies on this: re-claiming as the owner extends the lease.
    b = InMemoryBackend()
    assert b.claim("t", "A", ttl=10, now=0) is True
    assert b.claim("t", "A", ttl=10, now=5) is True    # refresh -> expires at 15
    assert b.claim("t", "B", ttl=10, now=12) is False  # would've expired at 10; still held
    assert b.claim("t", "B", ttl=10, now=16) is True   # now truly expired


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


# --- follow-ups: downstream-of-failure skip + heartbeat -----------------------


def test_worker_skips_downstream_of_failure_transitively():
    org = Ormica("HQ")
    Est = ArtifactType("e", {"n": int})
    org._tasks = [
        Task(description="a", id="a", produces=Est),          # will fail
        Task(description="b", id="b", depends_on=["a"]),       # blocked by a
        Task(description="c", id="c", depends_on=["b"]),       # blocked by b
        Task(description="indep", id="d"),                     # unrelated, still runs
    ]
    ran = []

    def reply(messages):
        ran.append(messages[-1].content)
        return "not json"  # a can't parse to Est -> a fails

    tally = org.run_worker(brain=MockBrain(reply_fn=reply), worker_id="w1")

    tasks = {t.id: t for t in org.load_tasks()}
    assert tasks["a"].status == "failed"
    assert tasks["b"].status == "failed" and "skipped: prerequisite a failed" in tasks["b"].error
    assert tasks["c"].status == "failed" and "skipped: prerequisite b failed" in tasks["c"].error
    assert tasks["d"].status == "done"          # independent work is unaffected
    assert "b" not in ran and "c" not in ran    # skipped tasks never hit the brain
    assert tally.processed == 4 and tally.failed == 3 and tally.succeeded == 1


def test_heartbeat_can_be_disabled_and_default_runs_clean():
    # heartbeat is on by default; the run must still complete cleanly. With the
    # default lease_ttl the beat interval is far longer than the tasks, so it
    # simply starts and stops per task without interfering.
    org = Ormica("HQ")
    for i in range(3):
        org.task(f"t{i}")
    tally = org.run_worker(
        brain=MockBrain(reply_fn=lambda m: "ok"), worker_id="w1", heartbeat=False
    )
    assert tally.processed == 3 and tally.succeeded == 3
