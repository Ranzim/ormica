"""
mycelium — shared memory.

The invisible connective layer that links every agent. Agents read
and write knowledge here; old signals decay over time. Memory persists
across sessions so the system learns.

Biological metaphor: the underground fungal network connecting trees.
"""

from .backend import Backend, InMemoryBackend
from .entry import Entry
from .file_backend import FileBackend
from .mycelium import Mycelium, Scope
from .sqlite_backend import SqliteBackend

__all__ = [
    "Backend",
    "Entry",
    "FileBackend",
    "InMemoryBackend",
    "Mycelium",
    "Scope",
    "SqliteBackend",
]
