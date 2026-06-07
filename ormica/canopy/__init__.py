"""
canopy — permission and root control.

Before any agent spawns a sub-agent, the request rises up the tree
to the appropriate authority — sometimes the parent, sometimes the
root owner. canopy assesses risk and routes approval, preventing
uncontrolled agent growth.

Biological metaphor: the forest canopy that controls light and growth below.
"""

from .approver import (
    Approver,
    AutoApprover,
    CallbackApprover,
    ConsoleApprover,
    DenyApprover,
)
from .policy import Canopy
from .risk import RiskAssessor, RiskLevel, RoleRisk, SpawnRequest, StaticRisk

__all__ = [
    "Approver",
    "AutoApprover",
    "CallbackApprover",
    "Canopy",
    "ConsoleApprover",
    "DenyApprover",
    "RiskAssessor",
    "RiskLevel",
    "RoleRisk",
    "SpawnRequest",
    "StaticRisk",
]
