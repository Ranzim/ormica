"""Secret redaction — keep API keys out of persisted traces and memory.

An agent's prompt or a tool's output can contain a credential (a pasted key, a
``Bearer`` header). The Thought Trail persists that reasoning to mycelium, so
without care a secret can end up written to disk. :func:`redact` masks the
credential *shapes* the ecosystem actually uses — high-signal prefixes, so
false positives are rare — before anything is stored.

    redact("my key is sk-ant-abc123...")   # → "my key is «redacted:anthropic-key»"

Applied automatically when a :class:`~ormica.observe.TraceObserver` persists a
trace; also usable directly on any string or nested structure (:func:`redact_deep`).
"""
from __future__ import annotations

import re
from typing import Any

# (label, compiled pattern) — ordered most-specific first so e.g. sk-ant- wins
# over the generic sk- rule.
_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{16,}")),
    ("openai-key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9\-_]{20,}")),
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("bearer-token", re.compile(r"[Bb]earer\s+[A-Za-z0-9\-._~+/]{16,}=*")),
]


def redact(text: str) -> str:
    """Mask credential-shaped substrings in ``text``. Non-strings pass through."""
    if not isinstance(text, str) or not text:
        return text
    out = text
    for label, pat in _PATTERNS:
        out = pat.sub(f"«redacted:{label}»", out)
    return out


def redact_deep(obj: Any) -> Any:
    """Recursively :func:`redact` every string inside dicts / lists / tuples."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_deep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_deep(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(redact_deep(v) for v in obj)
    return obj
