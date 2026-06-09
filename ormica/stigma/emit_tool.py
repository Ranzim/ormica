"""LLM-facing emit_signal tool — Option D from the v0.3 design memo.

Static yaml ``emits:`` (Option B, shipped) fires the same trail on every
task finalize regardless of what the agent thought. This module is the
richer half: an ``emit_signal`` tool the LLM can call mid-turn to
reinforce trails the agent itself deems noteworthy.

Production-grade constraints baked in:

- **Bounded vocabulary** — the tool's JSON schema declares the allowed
  topics as a typed enum. The LLM cannot invent topic names; auditors
  see the full vocabulary at colony-build time. Yaml-as-policy.
- **Strength bounds** — strength must lie in ``(0, max_strength]``.
  Zero or negative strengths silently no-op in :meth:`Stigma.reinforce`;
  unbounded strength would let one turn dominate the signal landscape.
- **Per-turn rate limit** — the builder's ``reset()`` is called by the
  runtime before each agent task. After ``max_per_turn`` emits, further
  calls return a polite refusal that the LLM sees as a tool result.
- **Refusals are not errors** — vocab violations, rate-limit hits, and
  out-of-range strengths all return a string the LLM reads. They do
  NOT raise — letting the model adjust its next call. Audit-friendly.

The tool's call record lives in ``TraceEntry.response_tool_calls``
automatically; the trace observer captures it without extra wiring.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ormica.arbor import Node
from ormica.brain import Tool

from .stigma import Stigma


@dataclass(frozen=True)
class EmitToolConfig:
    """Declarative config for the LLM-facing emit_signal tool.

    ``vocabulary`` is the bounded list of topic strings the LLM may emit.
    Listed in the tool's JSON-schema ``enum`` so a sensible model
    cannot invent new topics; an LLM that ignores the schema and tries
    anyway gets a refusal string back.
    """

    vocabulary: tuple[str, ...]
    max_per_turn: int = 3
    max_strength: float = 3.0
    default_strength: float = 1.0

    def __post_init__(self) -> None:
        if not self.vocabulary:
            raise ValueError("EmitToolConfig.vocabulary must be non-empty")
        if any(not isinstance(t, str) or not t for t in self.vocabulary):
            raise ValueError(
                "EmitToolConfig.vocabulary entries must be non-empty strings"
            )
        if self.max_per_turn < 1:
            raise ValueError(
                f"EmitToolConfig.max_per_turn must be >= 1, got {self.max_per_turn}"
            )
        if self.max_strength <= 0:
            raise ValueError(
                f"EmitToolConfig.max_strength must be > 0, got {self.max_strength}"
            )
        if not (0 < self.default_strength <= self.max_strength):
            raise ValueError(
                f"EmitToolConfig.default_strength must lie in (0, max_strength], "
                f"got {self.default_strength} with max_strength={self.max_strength}"
            )


class EmitToolBuilder:
    """Constructs a per-turn-stateful ``emit_signal`` Tool for one agent.

    The builder is intentionally per-agent-per-task: it owns the rate
    counter, which the runtime resets via :meth:`reset` before each
    ``act_with_tools`` invocation. Sharing one builder across tasks
    would pool the rate limit across tasks, breaking per-turn semantics.
    """

    def __init__(
        self,
        signals: Stigma,
        node: Node,
        config: EmitToolConfig,
    ) -> None:
        self.signals = signals
        self.node = node
        self.config = config
        self.emitted_this_turn: int = 0
        # Refusals emitted in this turn — exposed for the runtime to log.
        # Lets observability layers count "model tried but was refused"
        # cases distinctly from "model never tried."
        self.refusals: list[str] = []

    def reset(self) -> None:
        """Zero the per-turn counter. Runtime calls this before each task."""
        self.emitted_this_turn = 0
        self.refusals = []

    def __call__(self, topic: str, strength: Optional[float] = None) -> str:
        """The actual tool body. Returns a string the LLM reads as the result."""
        if strength is None:
            strength = self.config.default_strength
        # Validation order: check rate limit FIRST so a flood of malformed
        # calls still counts against the limit (prevents trivial DoS via
        # the tool surface).
        if self.emitted_this_turn >= self.config.max_per_turn:
            msg = (
                f"refused: rate limit — already emitted "
                f"{self.config.max_per_turn} signal(s) this turn"
            )
            self.refusals.append(msg)
            return msg
        if topic not in self.config.vocabulary:
            msg = (
                f"refused: unknown topic {topic!r}. "
                f"Vocabulary: {list(self.config.vocabulary)}"
            )
            self.refusals.append(msg)
            # A failed vocab check still counts so flood-attempts get
            # rate-limited.
            self.emitted_this_turn += 1
            return msg
        try:
            strength_f = float(strength)
        except (TypeError, ValueError):
            msg = f"refused: strength must be a number, got {strength!r}"
            self.refusals.append(msg)
            self.emitted_this_turn += 1
            return msg
        if not (0 < strength_f <= self.config.max_strength):
            msg = (
                f"refused: strength must be in (0, {self.config.max_strength}], "
                f"got {strength_f}"
            )
            self.refusals.append(msg)
            self.emitted_this_turn += 1
            return msg
        try:
            self.signals.reinforce(topic, amount=strength_f, by=self.node.id)
        except Exception as exc:
            # Stigma failure surfaces to the LLM rather than crashing the
            # tool loop — same swallow-philosophy as _maybe_auto_emit.
            msg = f"refused: stigma write failed: {type(exc).__name__}: {exc}"
            self.refusals.append(msg)
            self.emitted_this_turn += 1
            return msg
        self.emitted_this_turn += 1
        return f"ok: reinforced {topic!r} at strength {strength_f}"

    def as_tool(self) -> Tool:
        """Materialize the configured emit function as a Tool the LLM sees.

        JSON schema declares ``topic`` as a typed enum (the vocabulary)
        and ``strength`` with explicit bounds — capable models will
        respect both without needing a refusal round-trip.
        """
        vocab = list(self.config.vocabulary)
        description = (
            "Emit a colony coordination signal that other agents in the "
            "colony may sense. Use this when you observe something the "
            "rest of the colony should know about (a trend, a milestone, "
            "a risk worth tracking). Each call reinforces a stigma trail; "
            "repeated calls on the same topic accumulate strength. "
            f"Available topics: {vocab}. "
            f"strength must lie in (0, {self.config.max_strength}]; "
            f"defaults to {self.config.default_strength}. "
            f"You may call this at most {self.config.max_per_turn} time(s) per turn."
        )
        schema = {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": vocab,
                    "description": (
                        "The colony topic to emit. Must be one of the "
                        "declared vocabulary values."
                    ),
                },
                "strength": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "maximum": self.config.max_strength,
                    "default": self.config.default_strength,
                    "description": (
                        f"Signal strength, strictly > 0 and "
                        f"<= {self.config.max_strength}."
                    ),
                },
            },
            "required": ["topic"],
        }
        return Tool(
            name="emit_signal",
            description=description,
            fn=self,
            schema=schema,
        )
