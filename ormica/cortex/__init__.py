"""
cortex — constitutional governance.

The colony's law: hard constraints and soft policies that constrain what
agents may do, regardless of what their brains generate. Where ``brain``
*produces* responses, ``cortex`` *enforces* what's permissible.

Use :class:`Constitution` to gather :class:`Rule` objects; consult it at
runtime via :meth:`Constitution.enforce` (raises on hard violations) or
via :class:`ConstitutionPolicy` to also govern tree growth.

Biological metaphor: the cerebral cortex — the executive layer that
inhibits impulses generated lower in the brain.
"""

from .constitution import Constitution
from .policy import ConstitutionPolicy
from .rule import Rule, RulePredicate, RuleViolation, Violation

__all__ = [
    "Constitution",
    "ConstitutionPolicy",
    "Rule",
    "RulePredicate",
    "RuleViolation",
    "Violation",
]
