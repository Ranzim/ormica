"""Rule — one constitutional constraint."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

# A rule predicate takes a context dict (whatever the caller chose to expose)
# and returns True if the action is allowed.
RulePredicate = Callable[[dict], bool]


@dataclass
class Rule:
    """A single constraint encoded as a predicate over a context dict.

    The ``check`` callable returns ``True`` when the action is permitted.
    A returned ``False`` (or a raised exception) becomes a :class:`Violation`.

    ``stage`` decides when the constitution evaluates the rule:

    - ``"pre"`` (default) — before an action (think call, spawn) is performed
    - ``"post"`` — after, with the result available in the context
    - ``"spawn"`` — only on tree growth (via the SpawnPolicy seam)

    ``severity`` is informational for observability; ``hard`` rules raise
    :class:`RuleViolation`, ``soft`` rules emit an event and the action proceeds.

    **Context schema** (the dict passed to ``check``):

    ``stage="spawn"`` — built by :class:`ConstitutionPolicy`:

    - ``parent`` (``Node``) — the parent of the proposed child
    - ``child_name`` (``str``) — name of the proposed child
    - ``depth`` (``int``) — depth of the proposed child (``parent.depth + 1``)
    - ``role`` (``str``) — role of the proposed child (empty string if none)
    - ``task_text`` (``str``) — free-text task carried on the spawning node (empty if none)

    ``stage="pre"`` — built by the agent before each think call:

    - ``node`` (``Node``) — the agent's node
    - ``role`` (``str``) — ``node.role``
    - ``task_text`` (``str``) — ``node.task`` (the spawn-time string)
    - ``task`` (``runtime.Task`` | ``None``) — the runtime Task object when driven
      by a runner; ``None`` when an Agent is used directly
    - ``prompt`` (``Prompt``) — the prompt passed to ``agent.act``
    - ``budget`` (``TokenBudget`` | ``None``) — the agent's token budget

    ``stage="post"`` — built by the agent after a successful think call. For
    ``act_with_tools`` this fires only on the final (text) response, not on
    intermediate tool-use responses. Same keys as pre, plus:

    - ``response`` (``Response``) — the brain's response; ``response.content``
      is the model's text, ``response.tokens_used`` is the call's token cost
    - ``budget`` here reflects post-debit: ``response.tokens_used`` has already
      been consumed before the post-stage rule runs
    """

    name: str
    description: str
    check: RulePredicate = field(repr=False)
    stage: str = "pre"
    severity: str = "hard"  # "hard" | "soft"

    def evaluate(self, context: dict) -> Optional["Violation"]:
        try:
            ok = bool(self.check(context))
        except Exception as exc:  # noqa: BLE001 — surface as a violation, not a crash
            return Violation(rule=self, reason=f"{type(exc).__name__}: {exc}", context=context)
        if ok:
            return None
        return Violation(rule=self, reason="check returned False", context=context)


@dataclass
class Violation:
    """A failed rule evaluation."""

    rule: Rule
    reason: str
    context: dict = field(default_factory=dict, repr=False)

    def __str__(self) -> str:
        return f"{self.rule.name}: {self.reason}"


class RuleViolation(Exception):
    """Raised when a hard rule fails. Carries one or more :class:`Violation`."""

    def __init__(self, violations: list[Violation]) -> None:
        self.violations = violations
        super().__init__("; ".join(str(v) for v in violations))
