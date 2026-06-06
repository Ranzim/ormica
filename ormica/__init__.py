"""
Ormica — An Autonomous Coordination Engine.

Seed the colony. Let the organization emerge.

Quick start:
    from ormica import Ormica
    from ormica.brain import ClaudeBrain

    org = Ormica("My Company", owner="Founder")
    org.plant("business")
    org.task("Follow up with 3 leads", dept="sales", priority="high")
    org.run(brain=ClaudeBrain())

Docs: https://github.com/Ranzim/ormica/tree/master/docs
"""

__version__ = "0.1.1rc1"

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
