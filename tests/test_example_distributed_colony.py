"""Smoke test for the distributed-colony example (examples/distributed_colony/run.py).

Runs it as a subprocess (exactly how a user runs it, so `spawn` workers can
re-import cleanly) and proves every job completes exactly once — the
multi-process claim/lease coordination isn't vacuous.
"""
import subprocess
import sys
from pathlib import Path

from ormica import Ormica
from ormica.mycelium import Mycelium, SqliteBackend

_RUN = Path(__file__).resolve().parents[1] / "examples" / "distributed_colony" / "run.py"


def test_example_drains_queue_across_processes(tmp_path):
    db = str(tmp_path / "colony.db")
    proc = subprocess.run(
        [sys.executable, str(_RUN),
         "--workers", "3", "--jobs", "6", "--work-ms", "1", "--db", db],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr

    # verify from the shared store: each job done exactly once, correct answer
    org = Ormica("check", memory=Mycelium(backend=SqliteBackend(db)))
    tasks = {t.id: t for t in org.load_tasks()}
    assert len(tasks) == 6
    for i in range(6):
        t = tasks[f"job-{i:02d}"]
        assert t.status == "done"
        assert t.result.startswith(str(i * i))  # square of i, stamped by a worker
