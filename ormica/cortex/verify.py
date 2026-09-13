"""The ``verify`` stage — check a response and retry on failure.

Where the ``post`` stage is *terminal* (a hard failure raises and the turn is
over), the ``verify`` stage is *corrective*: when a verify rule fails, the
agent re-prompts the brain with the failure reason and tries again, up to
``max_verify_attempts``. Only if every attempt fails does it raise
:class:`VerificationFailed`.

This is what lets a colony produce *checkable* output for hard tasks —
"the answer must be valid JSON", "the code must compile", "the claim must
cite a source", "the sandbox run must pass" — instead of accepting the first
plausible-looking response.

A verify rule is an ordinary :class:`~ormica.cortex.Rule` with
``stage="verify"``; its ``check`` returns ``True`` when the response is
acceptable. The context dict it receives is the ``post`` context plus:

- ``attempt`` (``int``) — 1-based attempt number.

Use the factories below, or :func:`verifier` for anything custom (including
an LLM-as-judge that calls a brain inside the predicate).
"""
from __future__ import annotations

import json
import re
from typing import Callable, Pattern, Union

from .rule import Rule, Violation


class VerificationFailed(Exception):
    """Raised when a response fails verification after every retry.

    Carries the final :class:`Violation` list and the number of ``attempts``
    made, so callers can distinguish "gave up after retrying" from a hard
    :class:`~ormica.cortex.RuleViolation` (a constraint that blocks outright).
    """

    def __init__(self, violations: list[Violation], *, attempts: int) -> None:
        self.violations = violations
        self.attempts = attempts
        joined = "; ".join(str(v) for v in violations)
        super().__init__(f"verification failed after {attempts} attempt(s): {joined}")


def _response_text(context: dict) -> str:
    response = context.get("response")
    return getattr(response, "content", "") or ""


def verifier(
    name: str,
    check: Callable[[dict], bool],
    *,
    description: str = "",
    severity: str = "hard",
) -> Rule:
    """A custom verify rule from a predicate over the verify context.

    The predicate receives the full context (``response``, ``attempt``, ``node``,
    ``prompt``, …) and returns ``True`` when the response passes. Use this for
    domain checks — compile the code, run the sandbox, or call a brain as a judge.
    """
    return Rule(
        name=name,
        description=description or f"verify: {name}",
        check=check,
        stage="verify",
        severity=severity,
    )


def must_match(pattern: Union[str, Pattern], *, name: str = "must_match") -> Rule:
    """Response text must match ``pattern`` (``re.search``)."""
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern

    def check(context: dict) -> bool:
        return compiled.search(_response_text(context)) is not None

    return verifier(
        name, check, description=f"response must match /{compiled.pattern}/"
    )


def must_contain(text: str, *, name: str = "must_contain") -> Rule:
    """Response text must contain the substring ``text`` (case-insensitive)."""
    needle = text.lower()

    def check(context: dict) -> bool:
        return needle in _response_text(context).lower()

    return verifier(name, check, description=f"response must contain {text!r}")


def must_be_json(*, name: str = "must_be_json") -> Rule:
    """Response text must parse as JSON."""

    def check(context: dict) -> bool:
        text = _response_text(context).strip()
        if not text:
            return False
        try:
            json.loads(text)
        except (ValueError, TypeError):
            return False
        return True

    return verifier(name, check, description="response must be valid JSON")
