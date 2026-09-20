"""ClaimableBackend — atomic leases for stigmergic coordination.

Distributed execution in Ormica has no central dispatcher. Many workers share
one mycelium and coordinate *through the substrate*: to run a task, a worker
must first win an exclusive **lease** on it, so two workers never run the same
task. A lease has a TTL — if a worker dies mid-task, the lease expires and
another worker reclaims the work.

This is the stigmergic version of a work queue: coordination is a property of
the shared environment, not messages between workers. A backend advertises the
capability by implementing :class:`ClaimableBackend` (mirrors how
:class:`~ormica.mycelium.SearchableBackend` adds search). ``InMemoryBackend``
(in-process, lock-based) and ``SqliteBackend`` (cross-process, atomic) ship
with it.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ClaimableBackend(Protocol):
    """A backend that can grant exclusive, expiring leases on a key.

    ``claim`` and ``release`` must be atomic with respect to concurrent callers
    (threads for in-memory; processes for sqlite), so exactly one caller can
    hold a key's lease at a time.
    """

    def claim(self, key: str, owner: str, *, ttl: float, now: float) -> bool:
        """Grant ``owner`` an exclusive lease on ``key`` until ``now + ttl``.

        Returns ``True`` if the lease was granted — either because it was
        unheld, already held by ``owner`` (a heartbeat/refresh), or the previous
        holder's lease had expired at ``now``. Returns ``False`` if another
        owner holds a still-valid lease.
        """
        ...

    def release(self, key: str, owner: str) -> bool:
        """Release ``owner``'s lease on ``key``. Returns ``True`` if released."""
        ...
