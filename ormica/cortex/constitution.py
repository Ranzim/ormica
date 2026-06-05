"""Constitution — the colony's ruleset."""
from __future__ import annotations

from typing import Iterable, Optional

from .rule import Rule, RuleViolation, Violation


class Constitution:
    """A collection of :class:`Rule` objects evaluated as a unit.

    Add rules at construction or via :meth:`add`. Call :meth:`check`
    with a context dict to get back a list of :class:`Violation`. If any
    hard rule failed, :meth:`enforce` raises :class:`RuleViolation`.
    """

    def __init__(self, rules: Optional[Iterable[Rule]] = None) -> None:
        self._rules: list[Rule] = list(rules) if rules else []

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)

    def add(self, rule: Rule) -> None:
        self._rules.append(rule)

    def for_stage(self, stage: str) -> list[Rule]:
        return [r for r in self._rules if r.stage == stage]

    def check(self, context: dict, *, stage: str = "pre") -> list[Violation]:
        """Run every rule matching ``stage`` and return all violations."""
        out: list[Violation] = []
        for rule in self.for_stage(stage):
            v = rule.evaluate(context)
            if v is not None:
                out.append(v)
        return out

    def enforce(self, context: dict, *, stage: str = "pre") -> list[Violation]:
        """Check and raise :class:`RuleViolation` if any hard rule failed.

        Returns the soft-rule violations (which the caller can log / emit).
        """
        violations = self.check(context, stage=stage)
        hard = [v for v in violations if v.rule.severity == "hard"]
        if hard:
            raise RuleViolation(hard)
        return [v for v in violations if v.rule.severity == "soft"]

    def __len__(self) -> int:
        return len(self._rules)

    def __iter__(self):
        return iter(self._rules)
