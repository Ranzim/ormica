"""Regression: many processes/threads opening one SQLite file must not crash.

The benchmark surfaced a "database is locked" during `PRAGMA journal_mode=WAL`
when distributed workers all open the shared DB at once. Init now retries, so a
concurrent-open storm succeeds.
"""
import threading

from ormica.mycelium import SqliteBackend


def test_many_concurrent_opens_of_same_db(tmp_path):
    path = tmp_path / "colony.db"
    errors: list = []
    backends: list = []
    lock = threading.Lock()

    def open_one():
        try:
            b = SqliteBackend(path)
            with lock:
                backends.append(b)
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=open_one) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent open failed: {errors[:2]}"
    assert len(backends) == 16
    for b in backends:
        b.close()
