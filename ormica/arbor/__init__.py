"""
arbor — the tree structure.

The skeleton of every Ormica system. Provides the Node (single agent),
Branch (subtree view), and Tree (root + index + growth rules).
Trees grow to N depth; arbor enforces depth limits and routes spawn
requests through a SpawnPolicy that canopy plugs into.

Biological metaphor: a tree growing branches toward light.
"""

from .branch import Branch
from .exceptions import ArborError, MaxDepthExceeded, NodeNotFound, SpawnDenied
from .node import Node, NodeState
from .policy import AllowAllPolicy, SpawnPolicy
from .tree import Tree

__all__ = [
    "AllowAllPolicy",
    "ArborError",
    "Branch",
    "MaxDepthExceeded",
    "Node",
    "NodeNotFound",
    "NodeState",
    "SpawnDenied",
    "SpawnPolicy",
    "Tree",
]
