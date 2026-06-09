"""Declarative rule loader — translate YAML/JSON-style rule specs into :class:`Rule` objects.

This is what makes "YAML Constitutions" work. Users name rule-library
primitives by name and pass their arg in declarative form; the loader
turns the list into a fully-formed :class:`Constitution`.

YAML::

    constitution:
      rules:
        - max_depth: 4
        - max_tokens: 100000
        - block_role: finance
        - banned_words: [secret, confidential]
        - require_json                # zero-arg form
        - {max_response_tokens: 800, severity: soft}   # warn + record, no fail

Each entry is either:

- a bare string — names a zero-arg factory
- a single-key mapping — names a factory; the value is its positional arg
- a two-key mapping with ``severity: hard|soft`` alongside the factory key —
  overrides the default ``"hard"`` severity. ``soft`` rules emit a
  ``rule.soft_violation`` event and the action proceeds; ``hard`` rules
  (default) raise :class:`RuleViolation`. Soft is for guidance you want
  surfaced and audited but not enforced ("this response was unusually long
  but we shipped it anyway"); hard is for non-negotiable constraints.

Complex args (compiled regex, custom predicate code) require Python; the
YAML form covers the common cases. To extend the registry from a plugin,
add an entry to :data:`RULE_FACTORIES` before loading.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable

from . import rules as _R
from .constitution import Constitution
from .rule import Rule

# Sentinel: "no argument was provided in the YAML" (distinct from `None`,
# which a future zero-arg factory might legitimately accept as `arg=None`).
_MISSING = object()

_VALID_SEVERITIES = ("hard", "soft")


# Public registry of rule factories nameable from YAML.
# Single-arg factories receive their positional arg as the YAML value;
# zero-arg factories are named bare (string) or with a null value.
RULE_FACTORIES: dict[str, Any] = {
    # spawn
    "max_depth": _R.max_depth,
    "block_role": _R.block_role,
    "no_child_name": _R.no_child_name,
    "unique_role_in_subtree": _R.unique_role_in_subtree,
    # pre
    "max_tokens": _R.max_tokens,
    "block_prompt_pattern": _R.block_prompt_pattern,
    "min_task_description": _R.min_task_description,
    "min_runtime_task_description": _R.min_runtime_task_description,
    # post
    "banned_words": _R.banned_words,
    "banned_word_stems": _R.banned_word_stems,
    "max_response_tokens": _R.max_response_tokens,
    "min_response_length": _R.min_response_length,
    "require_json": _R.require_json,
}


def build_rule(spec: Any) -> Rule:
    """Translate one declarative rule spec into a :class:`Rule`.

    Accepts:

    - a bare factory name (string) — e.g. ``"require_json"``
    - a single-key mapping — e.g. ``{"max_depth": 4}``
    - a mapping with ``severity: hard|soft`` plus exactly one factory
      key — e.g. ``{"max_response_tokens": 800, "severity": "soft"}``

    Raises :class:`ValueError` for unknown factories, malformed specs,
    or unrecognized severity values.
    """
    severity = "hard"  # the default; overridden if spec carries `severity:`
    if isinstance(spec, str):
        name, arg = spec, _MISSING
    elif isinstance(spec, dict):
        # Extract a severity sibling if present, leaving the rest of the
        # mapping to look like a single-key spec for normal handling.
        rest = dict(spec)
        if "severity" in rest:
            severity = rest.pop("severity")
            if severity not in _VALID_SEVERITIES:
                raise ValueError(
                    f"rule severity must be one of {list(_VALID_SEVERITIES)}, "
                    f"got {severity!r}"
                )
        if len(rest) == 1:
            name, raw = next(iter(rest.items()))
            arg = _MISSING if raw is None else raw
        else:
            raise ValueError(
                f"rule spec must be a string, a single-key mapping, or a "
                f"two-key mapping with 'severity' + one factory key; "
                f"got {spec!r}"
            )
    else:
        raise ValueError(
            f"rule spec must be a string or mapping, got {spec!r}"
        )

    factory = RULE_FACTORIES.get(name)
    if factory is None:
        available = ", ".join(sorted(RULE_FACTORIES))
        raise ValueError(
            f"unknown rule {name!r}. Available: {available}"
        )

    rule = factory() if arg is _MISSING else factory(arg)
    if severity != "hard":
        # Rule is a frozen dataclass; replace() returns a new instance
        # with the severity field overridden, keeping name/description/
        # check/stage intact.
        rule = replace(rule, severity=severity)
    return rule


def build_constitution(specs: Iterable[Any]) -> Constitution:
    """Build a :class:`Constitution` from a list of declarative rule specs."""
    return Constitution([build_rule(spec) for spec in specs])
