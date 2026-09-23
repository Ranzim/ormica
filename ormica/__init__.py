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

__version__ = "0.11.0"

from ormica.agent import Agent, AsyncAgent
from ormica.artifact import Artifact, ArtifactError, ArtifactType
from ormica.core import Ormica
from ormica.delegation import DelegationBuilder
from ormica.distributed import DistributedWorker
from ormica.evolution import EvolutionResult, Genome, evolve
from ormica.forest import Forest, ForestResult, Vote, majority_vote, unanimous
from ormica.healing import HealingPolicy
from ormica.learning import StigmergicRouter, route_reward
from ormica.planner import (
    AsyncPlanner,
    Plan,
    PlanError,
    PlannedStep,
    Planner,
)
from ormica.postbox import Message, Postbox
from ormica.preferences import Preferences
from ormica.redact import redact, redact_deep
from ormica.runtime import AsyncDagRunner, RunResult, Task

__all__ = [
    "Agent",
    "Artifact",
    "ArtifactError",
    "ArtifactType",
    "AsyncAgent",
    "AsyncDagRunner",
    "AsyncPlanner",
    "DelegationBuilder",
    "DistributedWorker",
    "EvolutionResult",
    "Forest",
    "ForestResult",
    "Genome",
    "HealingPolicy",
    "Message",
    "Ormica",
    "Plan",
    "PlanError",
    "PlannedStep",
    "Planner",
    "Postbox",
    "Preferences",
    "RunResult",
    "StigmergicRouter",
    "Task",
    "Vote",
    "__version__",
    "evolve",
    "majority_vote",
    "redact",
    "redact_deep",
    "route_reward",
    "unanimous",
]
