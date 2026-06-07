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
    """Reject runs whose node carries a *spawn-time* task string shorter than ``n``.

    Reads ``ctx["task_text"]`` — the static ``Node.task`` set at spawn
    time (e.g. via a colony template's ``task:`` field). This is NOT
    the runtime task description submitted via ``org.task(description=…)``.
    For that, use :func:`min_runtime_task_description`.

    Why both exist: ``Node.task`` is a fixed role-description ("Handle
    billing tickets"); the runtime task description is the specific ask
    on each invocation ("Process refund for order #1234"). Same word,
    two different things — easy to confuse, so we keep them as
    sibling rules with names that read distinctly.
    """
    return Rule(
        name=f"min_task_description_{n}",
        description=(
            f"Node spawn-time task string must be at least {n} characters."
        ),
        check=lambda ctx: len(ctx.get("task_text", "")) >= n,
        stage="pre",
    )


def min_runtime_task_description(n: int) -> Rule:
    """Reject runs whose runtime task description is shorter than ``n`` chars.

    Reads ``ctx["task"].description`` — the per-invocation task string
    set when the user called ``org.task(description=…)``. Use this when
    you want to reject one-word briefs at submission time
    ("update the doc" → too vague to act on).

    For the static spawn-time variant (``Node.task``), use
    :func:`min_task_description`.
    """
    def _check(ctx) -> bool:
        task = ctx.get("task")
        # When driven directly (no runner), ctx["task"] is None — treat as
        # "no runtime task to inspect" and pass. Pre-stage rules running
        # outside a runner don't have a description to enforce against.
        if task is None:
            return True
        return len(getattr(task, "description", "") or "") >= n

    return Rule(
        name=f"min_runtime_task_description_{n}",
        description=(
            f"Runtime task description (org.task(description=...)) must be "
            f"at least {n} characters."
        ),
        check=_check,
        stage="pre",
    )


# --- post-stage rules ---------------------------------------------------------


def banned_words(words: Iterable[str]) -> Rule:
    """Reject responses containing any of ``words`` (case-insensitive *substring*).

    Reads ``ctx["response"].content``. Substring match catches partial
    phrases (``"unguaranteed"`` is caught by ``"guarantee"``) but does
    NOT do morphological matching: ``"guaranteed"`` will not catch
    ``"guaranteeing"``. List both stems when both matter, or use
    :func:`banned_word_stems` for whole-word + suffix matching.

    Cost: this is a post-stage rule, which means the LLM call has
    already happened by the time the check runs — token spend is sunk
    even if the response is rejected. For known-banned content where
    you can match on the *prompt*, use ``block_prompt_pattern`` instead
    to fail before the LLM call.
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


def banned_word_stems(words: Iterable[str]) -> Rule:
    """Reject responses containing any of ``words`` *as whole words with
    optional suffixes* (case-insensitive).

    Compiles each entry as a regex ``\\bword\\w*\\b`` so a single stem
    catches its common suffix-only inflections:

      - ``"guarantee"`` → catches ``guarantee``, ``guarantees``,
        ``guaranteed``, ``guaranteeing`` (all keep the literal stem)
      - ``"miracle"`` → catches ``miracle``, ``miracles``,
        ``miraculous``
      - ``"cure"`` → catches ``cure``, ``cures``, ``cured`` but NOT
        ``curing`` (silent ``e`` is dropped before ``-ing``)

    Trade-offs vs :func:`banned_words` (substring): you GAIN catching
    suffix-added inflections without listing them; you LOSE substring
    matching inside other words (``"unguaranteed"`` is no longer
    flagged); and you do NOT get morphological stemming — when a suffix
    modifies the stem itself (silent-e drop before -ing/-ed, y→i
    changes), list both forms explicitly: ``["cure", "curing"]``.

    For most compliance use cases (FTC endorsements, health claims),
    suffix-only is what you want for ~70% of English verbs and the
    documented gotcha applies to the rest. If you need true linguistic
    stemming, write a custom rule with a Porter / Snowball stemmer.

    Cost: same post-stage caveat as :func:`banned_words` — the LLM has
    already been called by the time the check runs.
    """
    import re

    stems = [w.lower() for w in words if w]
    if not stems:
        # An empty-stems rule would pass every input — that's almost certainly
        # not what the caller intended. Reject loudly.
        raise ValueError("banned_word_stems requires at least one non-empty stem")
    # Each stem becomes \bstem\w*\b so it matches the stem followed by
    # zero-or-more word chars, bounded on both sides — catches
    # guarantee, guarantees, guaranteed, guaranteeing for stem="guarantee".
    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(s) + r"\w*" for s in stems) + r")\b",
        re.IGNORECASE,
    )
    label = ",".join(sorted(stems))[:48]
    return Rule(
        name=f"banned_word_stems_{label}",
        description=(
            f"Response must not contain any of these stems (with suffixes): "
            f"{sorted(stems)}."
        ),
        check=lambda ctx: pattern.search(ctx["response"].content) is None,
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
