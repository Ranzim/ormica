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

__version__ = "0.5.0"

from ormica.agent import Agent, AsyncAgent
from ormica.core import Ormica
from ormica.delegation import DelegationBuilder
from ormica.planner import (
    AsyncPlanner,
    Plan,
    PlanError,
    PlannedStep,
    Planner,
)
from ormica.postbox import Message, Postbox
from ormica.runtime import AsyncDagRunner, RunResult, Task

__all__ = [
    "Agent",
    "AsyncAgent",
    "AsyncDagRunner",
    "AsyncPlanner",
    "DelegationBuilder",
    "Message",
    "Ormica",
    "Plan",
    "PlanError",
    "PlannedStep",
    "Planner",
    "Postbox",
    "RunResult",
    "Task",
    "__version__",
]
