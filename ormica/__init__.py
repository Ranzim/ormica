"""
Ormica — build agentic software that organizes itself like an ant colony.

Quick start:
    from ormica import Ormica

    org = Ormica("My Company", owner="Founder")
    org.plant("supply_chain")
    org.run()
"""

__version__ = "0.0.1"

from ormica.agent import Agent, AsyncAgent
from ormica.core import Ormica
from ormica.runtime import RunResult, Task

__all__ = [
    "Agent",
    "AsyncAgent",
    "Ormica",
    "RunResult",
    "Task",
    "__version__",
]
