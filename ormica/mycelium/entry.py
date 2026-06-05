"""An Entry — a single value in the shared memory."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any, Optional


@dataclass
class Entry:
    """One record in mycelium.

    ``author`` is the id of the node that wrote it (or None for the system).
    ``expires_at`` is wall-clock seconds since epoch; ``None`` means never expires.
    """

    key: str
    value: Any
    author: Optional[str] = None
    written_at: float = field(default_factory=time)
    expires_at: Optional[float] = None
    meta: dict = field(default_factory=dict)

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.expires_at is None:
            return False
        return (now if now is not None else time()) >= self.expires_at
