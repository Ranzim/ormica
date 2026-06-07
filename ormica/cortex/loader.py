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

Each entry is either:

- a bare string — names a zero-arg factory
- a single-key mapping — names a factory; the value is its positional arg

Complex args (compiled regex, custom predicate code) require Python; the
YAML form covers the common cases. To extend the registry from a plugin,
add an entry to :data:`RULE_FACTORIES` before loading.
"""
from __future__ import annotations

from typing import Any, Iterable

from . import rules as _R
from .constitution import Constitution
from .rule import Rule

# Sentinel: "no argument was provided in the YAML" (distinct from `None`,
# which a future zero-arg factory might legitimately accept as `arg=None`).
_MISSING = object()


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

    Accepts either a bare factory name (string) or a single-key mapping
    whose key is the factory name and value is the positional argument.
    Raises :class:`ValueError` for unknown factories or malformed specs.
    """
    if isinstance(spec, str):
        name, arg = spec, _MISSING
    elif isinstance(spec, dict) and len(spec) == 1:
        name, raw = next(iter(spec.items()))
        arg = _MISSING if raw is None else raw
    else:
        raise ValueError(
            f"rule spec must be a string or single-key mapping, got {spec!r}"
        )

    factory = RULE_FACTORIES.get(name)
    if factory is None:
        available = ", ".join(sorted(RULE_FACTORIES))
        raise ValueError(
            f"unknown rule {name!r}. Available: {available}"
        )

    return factory() if arg is _MISSING else factory(arg)


def build_constitution(specs: Iterable[Any]) -> Constitution:
    """Build a :class:`Constitution` from a list of declarative rule specs."""
    return Constitution([build_rule(spec) for spec in specs])
