"""
colony — pre-built agents per industry.

This is where industries plug in. The core engine is industry-agnostic;
colony provides ready-made agents for business, supply chain, healthcare,
and more. Define a new colony to support any industry.

Biological metaphor: a structured living community.
"""

from .base import AgentTemplate, Colony
from .registry import colonies, get_colony, register
from .yaml_loader import load_colony

# Importing these modules triggers ``@register`` on the concrete colonies.
from . import business, supply_chain  # noqa: F401, E402

__all__ = [
    "AgentTemplate",
    "Colony",
    "colonies",
    "get_colony",
    "load_colony",
    "register",
]
