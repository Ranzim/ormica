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
from .grounding import artifact_oracle, grounded, judge_oracle, sandbox_oracle
from .policy import ConstitutionPolicy
from .rule import CheckResult, Rule, RulePredicate, RuleViolation, Violation
from .verify import (
    VerificationFailed,
    must_be_json,
    must_contain,
    must_match,
    verifier,
)

__all__ = [
    "CheckResult",
    "Constitution",
    "ConstitutionPolicy",
    "Rule",
    "RulePredicate",
    "RuleViolation",
    "VerificationFailed",
    "Violation",
    "artifact_oracle",
    "grounded",
    "judge_oracle",
    "must_be_json",
    "must_contain",
    "must_match",
    "sandbox_oracle",
    "verifier",
]
