"""
stigma — ant-colony behavior.

Agents coordinate indirectly through signals left in shared memory,
like ants leaving pheromone trails. Strong trails are reinforced,
weak ones evaporate. Intelligence emerges from simple local rules.

Biological metaphor: stigmergy — how ants self-organize without a boss.
"""

from .signal import Signal
from .stigma import Stigma

__all__ = ["Signal", "Stigma"]
