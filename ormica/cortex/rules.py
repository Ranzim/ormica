"""Standard rule library — ready-made :class:`Rule` factories.

Each function returns a fully-formed :class:`Rule` you can drop into a
:class:`Constitution`. Names and descriptions are filled in for you;
violations surface meaningfully in `RuleViolation.violations`.

::

    from ormica.cortex import Constitution
    from ormica.cortex.rules import (
        max_depth,
        max_tokens,
        banned_words,
        require_json,
    )

    constitution = Constitution([
        max_depth(4),
        max_tokens(100_000),
        banned_words({"secret", "internal-only"}),
        require_json(),
    ])

These primitives cover the most common production needs without forcing
every project to re-implement them. Roll your own ``Rule`` for the cases
they don't cover — these are conveniences, not the only way.
"""
from __future__ import annotations

import json
import re
from typing import Iterable, Union

from .rule import Rule

# A pattern is either a substring (matched case-insensitively) or a
# compiled regex (used as-is). Both are supported by ``re.search``.
Pattern = Union[str, re.Pattern]


# --- spawn-stage rules --------------------------------------------------------


def max_depth(n: int) -> Rule:
    """Cap tree depth: spawning past depth ``n`` is denied.

    Reads ``ctx["depth"]`` — the proposed child's depth (``parent.depth + 1``).
    """
    return Rule(
        name=f"max_depth_{n}",
        description=f"Tree may not grow past depth {n}.",
        check=lambda ctx: ctx["depth"] <= n,
        stage="spawn",
    )


def block_role(role: str) -> Rule:
    """Prevent nodes with ``role`` from ever being spawned.

    Reads ``ctx["role"]`` — the role of the proposed child.
    """
    return Rule(
        name=f"block_role_{role}",
        description=f"Cannot spawn a node with role={role!r}.",
        check=lambda ctx: ctx["role"] != role,
        stage="spawn",
    )


def no_child_name(name: str) -> Rule:
    """Prevent any node from being spawned with the literal name ``name``.

    Useful when a particular name is reserved (``"root"``, ``"system"``…).
    Reads ``ctx["child_name"]``.
    """
    return Rule(
        name=f"no_child_name_{name}",
        description=f"Cannot spawn a node named {name!r}.",
        check=lambda ctx: ctx["child_name"] != name,
        stage="spawn",
    )


def unique_role_in_subtree(role: str) -> Rule:
    """Allow at most one node with ``role`` under any parent's subtree.

    Reads ``ctx["role"]`` and ``ctx["parent"]``; walks the parent's subtree
    looking for an existing match.
    """
    return Rule(
        name=f"unique_role_{role}",
        description=f"Only one node with role={role!r} allowed under any subtree.",
        check=lambda ctx: not (
            ctx["role"] == role
            and any(n.role == role for n in ctx["parent"].walk())
        ),
        stage="spawn",
    )


# --- pre-stage rules ----------------------------------------------------------


def max_tokens(n: int) -> Rule:
    """Cap total token spend across the org: ``ctx["budget"].used < n``.

    No-op if no budget is attached. Reads ``ctx["budget"]``.
    """
    return Rule(
        name=f"max_tokens_{n}",
        description=f"Total tokens spent must stay under {n}.",
        check=lambda ctx: ctx["budget"] is None or ctx["budget"].used < n,
        stage="pre",
    )


def block_prompt_pattern(pattern: Pattern) -> Rule:
    """Block any prompt matching ``pattern``.

    ``pattern`` may be a substring (case-insensitive ``re.search``) or a
    compiled ``re.Pattern``. Reads ``ctx["prompt"]``.
    """
    compiled = pattern if isinstance(pattern, re.Pattern) else re.compile(
        re.escape(pattern), re.IGNORECASE
    )
    display = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
    return Rule(
        name=f"block_prompt_{display}",
        description=f"Prompt must not match pattern {display!r}.",
        check=lambda ctx: compiled.search(_prompt_text(ctx["prompt"])) is None,
        stage="pre",
    )


def min_task_description(n: int) -> Rule:
    """Reject runs whose node carries a task string shorter than ``n`` chars.

    Reads ``ctx["task_text"]`` — the spawn-time ``Node.task`` string.
    """
    return Rule(
        name=f"min_task_description_{n}",
        description=f"Node task description must be at least {n} characters.",
        check=lambda ctx: len(ctx.get("task_text", "")) >= n,
        stage="pre",
    )


# --- post-stage rules ---------------------------------------------------------


def banned_words(words: Iterable[str]) -> Rule:
    """Reject responses containing any of ``words`` (case-insensitive substring).

    Reads ``ctx["response"].content``.
    """
    banned = {w.lower() for w in words}
    label = ",".join(sorted(banned))[:48]
    return Rule(
        name=f"banned_words_{label}",
        description=f"Response must not contain any of: {sorted(banned)}.",
        check=lambda ctx: not any(
            w in ctx["response"].content.lower() for w in banned
        ),
        stage="post",
    )


def max_response_tokens(n: int) -> Rule:
    """Cap a single response's token cost.

    Reads ``ctx["response"].tokens_used``.
    """
    return Rule(
        name=f"max_response_tokens_{n}",
        description=f"Single response must use ≤ {n} tokens.",
        check=lambda ctx: ctx["response"].tokens_used <= n,
        stage="post",
    )


def min_response_length(n: int) -> Rule:
    """Reject very short or empty responses.

    Reads ``ctx["response"].content``.
    """
    return Rule(
        name=f"min_response_length_{n}",
        description=f"Response content must be at least {n} characters.",
        check=lambda ctx: len(ctx["response"].content) >= n,
        stage="post",
    )


def require_json() -> Rule:
    """Reject responses whose content does not parse as JSON.

    Reads ``ctx["response"].content``. Useful for tool-output schemas where
    the model is expected to return a JSON object.
    """
    def _is_json(ctx: dict) -> bool:
        try:
            json.loads(ctx["response"].content)
            return True
        except (ValueError, TypeError):
            return False

    return Rule(
        name="require_json",
        description="Response content must parse as valid JSON.",
        check=_is_json,
        stage="post",
    )


# --- helpers ------------------------------------------------------------------


def _prompt_text(prompt) -> str:
    """Best-effort flatten of a Prompt to a single string for pattern matching."""
    if isinstance(prompt, str):
        return prompt
    try:
        return " ".join(getattr(m, "content", "") or "" for m in prompt)
    except TypeError:
        return str(prompt)
