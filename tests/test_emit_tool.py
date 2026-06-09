"""Tests for the LLM-facing emit_signal tool (Option D from v0.3 design memo).

Covers:
  - EmitToolConfig validation (vocab, bounds)
  - EmitToolBuilder semantics (ok, vocab gate, rate limit, strength bounds,
    stigma write failure, reset)
  - as_tool() shape (typed enum, JSON schema)
  - yaml loader: compact + explicit forms, error paths
  - AgentTemplate.plant() stamps emit_tool_config onto node.meta
  - Runtime switch: node with emit_tool_config → act_with_tools, without → act
  - End-to-end: yaml-declared vocab, MockBrain returns ToolCall, trail lands
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ormica import Ormica
from ormica.brain import MockBrain, ToolCall
from ormica.colony import load_colony
from ormica.stigma import EmitToolBuilder, EmitToolConfig


# --- EmitToolConfig validation ----------------------------------------------


def test_config_rejects_empty_vocabulary():
    with pytest.raises(ValueError, match="vocabulary must be non-empty"):
        EmitToolConfig(vocabulary=())


def test_config_rejects_non_string_vocab_entries():
    with pytest.raises(ValueError, match="non-empty strings"):
        EmitToolConfig(vocabulary=("ok", "", "also-ok"))
    with pytest.raises(ValueError, match="non-empty strings"):
        EmitToolConfig(vocabulary=("ok", 42))


def test_config_rejects_bad_max_per_turn():
    with pytest.raises(ValueError, match="max_per_turn must be >= 1"):
        EmitToolConfig(vocabulary=("a",), max_per_turn=0)


def test_config_rejects_non_positive_max_strength():
    with pytest.raises(ValueError, match="max_strength must be > 0"):
        EmitToolConfig(vocabulary=("a",), max_strength=0)
    with pytest.raises(ValueError, match="max_strength must be > 0"):
        EmitToolConfig(vocabulary=("a",), max_strength=-1.0)


def test_config_default_strength_must_lie_in_bounds():
    with pytest.raises(ValueError, match="default_strength must lie"):
        EmitToolConfig(vocabulary=("a",), max_strength=2.0, default_strength=3.0)
    with pytest.raises(ValueError, match="default_strength must lie"):
        EmitToolConfig(vocabulary=("a",), default_strength=0)


# --- EmitToolBuilder behavior ------------------------------------------------


def _builder(vocabulary=("trending", "brief"), **kw):
    org = Ormica("X", max_depth=3)
    leaf = org.spawn("leaf")
    cfg = EmitToolConfig(vocabulary=vocabulary, **kw)
    return EmitToolBuilder(org.signals, leaf, cfg), org, leaf


def test_ok_call_reinforces_signal():
    builder, org, leaf = _builder()
    result = builder("trending", strength=2.0)
    assert result.startswith("ok:")
    trails = {s.topic: s.strength for s in org.signals.trails()}
    assert trails["trending"] == pytest.approx(2.0, abs=0.01)


def test_ok_call_omitting_strength_uses_default():
    builder, org, _ = _builder(default_strength=1.0)
    result = builder("trending")
    assert result.startswith("ok:")
    trails = {s.topic: s.strength for s in org.signals.trails()}
    assert trails["trending"] == pytest.approx(1.0, abs=0.01)


def test_unknown_topic_refused_not_raised():
    """The whole point: refusals come back as strings the LLM reads, never raises."""
    builder, org, _ = _builder()
    result = builder("totally-made-up", strength=1.0)
    assert result.startswith("refused:")
    assert "unknown topic" in result
    # And no trail was written.
    assert org.signals.trails() == []


def test_rate_limit_kicks_in_after_max_per_turn():
    builder, org, _ = _builder(max_per_turn=2)
    assert builder("trending").startswith("ok:")
    assert builder("brief").startswith("ok:")
    third = builder("trending")
    assert third.startswith("refused:")
    assert "rate limit" in third


def test_rate_limit_counts_refused_calls_too():
    """A flood of malformed calls still consumes the budget — prevents DoS via
    the tool surface."""
    builder, _, _ = _builder(max_per_turn=3)
    builder("totally-made-up")  # refused
    builder("also-bogus")       # refused
    builder("trending")         # ok — but counts as the 3rd
    fourth = builder("trending")
    assert fourth.startswith("refused:")
    assert "rate limit" in fourth


def test_strength_out_of_range_refused():
    builder, _, _ = _builder(max_strength=2.0)
    assert builder("trending", strength=2.5).startswith("refused:")
    assert builder("trending", strength=0).startswith("refused:")
    assert builder("trending", strength=-1.0).startswith("refused:")


def test_non_numeric_strength_refused():
    builder, _, _ = _builder()
    assert builder("trending", strength="strong").startswith("refused:")


def test_reset_zeros_the_counter():
    builder, _, _ = _builder(max_per_turn=1)
    builder("trending")  # ok
    assert builder("brief").startswith("refused:")  # rate-limited
    builder.reset()
    assert builder("brief").startswith("ok:")  # post-reset, fresh budget


def test_refusals_are_logged_for_observability():
    """Both vocab refusals and rate-limit refusals land in the refusals log
    so observability layers can distinguish 'model tried but was rejected'
    from 'model never tried'."""
    builder, _, _ = _builder(max_per_turn=2)
    builder("bogus")              # vocab refusal (counts toward budget)
    builder("trending")           # ok — budget now full at 2
    builder("brief")              # rate-limited (budget exhausted)
    builder("trending")           # rate-limited
    # 1 vocab refusal + 2 rate-limit refusals = 3 logged.
    assert len(builder.refusals) == 3
    assert sum("unknown topic" in r for r in builder.refusals) == 1
    assert sum("rate limit" in r for r in builder.refusals) == 2


def test_stigma_write_failure_refused_not_raised(monkeypatch):
    builder, org, _ = _builder()

    def boom(*a, **kw):
        raise RuntimeError("stigma broke")
    monkeypatch.setattr(org.signals, "reinforce", boom)

    result = builder("trending")
    assert result.startswith("refused:")
    assert "stigma write failed" in result


# --- as_tool() shape ---------------------------------------------------------


def test_as_tool_returns_typed_enum_schema():
    builder, _, _ = _builder(vocabulary=("a", "b", "c"))
    tool = builder.as_tool()
    assert tool.name == "emit_signal"
    assert tool.schema["properties"]["topic"]["enum"] == ["a", "b", "c"]
    assert tool.schema["required"] == ["topic"]
    # Strength bounded
    s = tool.schema["properties"]["strength"]
    assert s["exclusiveMinimum"] == 0
    assert s["maximum"] == 3.0


def test_as_tool_callable_invokes_builder():
    builder, org, _ = _builder()
    tool = builder.as_tool()
    result = tool(topic="trending", strength=1.5)
    assert result.startswith("ok:")
    trails = {s.topic: s.strength for s in org.signals.trails()}
    assert trails["trending"] == pytest.approx(1.5, abs=0.01)


# --- yaml loader: emit_tool: --------------------------------------------------


def _load(tmp_path: Path, body: str):
    yml = tmp_path / "c.yaml"
    yml.write_text(body)
    return load_colony(yml)


def test_yaml_compact_form_vocab_only(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    emit_tool: [trending, brief, needs-review]
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    cfg = node.meta["emit_tool_config"]
    assert isinstance(cfg, EmitToolConfig)
    assert cfg.vocabulary == ("trending", "brief", "needs-review")
    assert cfg.max_per_turn == 3   # default


def test_yaml_explicit_mapping_form(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    emit_tool:
      vocabulary: [trending, brief]
      max_per_turn: 5
      max_strength: 4.0
      default_strength: 2.0
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    cfg = node.meta["emit_tool_config"]
    assert cfg.vocabulary == ("trending", "brief")
    assert cfg.max_per_turn == 5
    assert cfg.max_strength == 4.0
    assert cfg.default_strength == 2.0


def test_yaml_no_emit_tool_field_means_no_meta_entry(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: plain
    role: p
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    assert "emit_tool_config" not in node.meta


def test_yaml_explicit_missing_vocabulary_errors(tmp_path: Path):
    with pytest.raises(ValueError, match="must include a 'vocabulary' list"):
        _load(tmp_path, """
name: x
templates:
  - name: e
    role: e
    emit_tool:
      max_per_turn: 5
""")


def test_yaml_bad_type_errors(tmp_path: Path):
    with pytest.raises(ValueError, match="must be a list .* or a mapping"):
        _load(tmp_path, """
name: x
templates:
  - name: e
    role: e
    emit_tool: "just a string"
""")


def test_yaml_propagates_config_validation(tmp_path: Path):
    """An invalid EmitToolConfig (e.g. empty vocab) surfaces as a yaml ValueError."""
    with pytest.raises(ValueError, match="invalid emit_tool"):
        _load(tmp_path, """
name: x
templates:
  - name: e
    role: e
    emit_tool: []
""")


# --- runtime switch ---------------------------------------------------------


def test_runtime_uses_act_when_no_emit_tool(tmp_path: Path):
    """Back-compat: a node without emit_tool runs through plain act()."""
    cls = _load(tmp_path, """
name: x
templates:
  - name: plain
    role: p
    task: do something
""")
    org = Ormica("X", max_depth=3)
    cls().plant(org)
    org.task("hi", target="plain")
    result = org.run(brain=MockBrain(replies=["done"]))
    assert result.succeeded == 1
    # No signals from a node without emit_tool.
    assert org.signals.trails() == []


def test_runtime_uses_act_with_tools_when_emit_tool_declared(tmp_path: Path):
    """A node with emit_tool gets act_with_tools — MockBrain returns a
    ToolCall, which exercises the tool path and lands a stigma trail."""
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    task: emit a trend signal
    emit_tool: [trending, brief]
""")
    org = Ormica("X", max_depth=3)
    cls().plant(org)
    org.task("look around", target="emitter")

    # Reply schedule: first turn requests a tool call; second turn is the
    # final text answer. MockBrain cycles through these in order.
    brain = MockBrain(replies=[
        [ToolCall(id="call_1", name="emit_signal",
                  arguments={"topic": "trending", "strength": 1.5})],
        "Done reviewing trends.",
    ])
    result = org.run(brain=brain)
    assert result.succeeded == 1
    trails = {s.topic: s.strength for s in org.signals.trails()}
    assert "trending" in trails
    assert trails["trending"] == pytest.approx(1.5, abs=0.01)


def test_runtime_emit_tool_vocab_violation_is_recoverable(tmp_path: Path):
    """The LLM trying an unknown topic gets a refusal but the task continues."""
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    task: emit something
    emit_tool: [trending]
""")
    org = Ormica("X", max_depth=3)
    cls().plant(org)
    org.task("look around", target="emitter")

    brain = MockBrain(replies=[
        [ToolCall(id="c1", name="emit_signal",
                  arguments={"topic": "totally-made-up"})],
        "I'll stick to what I know.",
    ])
    result = org.run(brain=brain)
    # Task succeeded (refusal didn't crash); no trail was written for the
    # bogus topic (vocab gate held).
    assert result.succeeded == 1
    assert org.signals.trails() == []


# --- end-to-end: emit-tool node feeds a sensing node -------------------------


def test_llm_emitted_signal_visible_to_sensing_sibling(tmp_path: Path):
    """The bedrock claim: an LLM's tool call lands as a trail, a sibling
    with sense_prefixes reads it on its next turn. Pure yaml. No Python."""
    from ormica.observe import TraceObserver

    cls = _load(tmp_path, """
name: chain
templates:
  - name: scout
    role: scout
    task: report what's trending
    emit_tool: [trending]
  - name: watcher
    role: watcher
    task: react to trending signals
    sense_prefixes: ["trending"]
""")
    org = Ormica("X", max_depth=3)
    cls().plant(org)
    org.subscribe(TraceObserver(store=org.memory))

    # Scout's brain: first turn emits, second turn answers.
    # Watcher's brain: just answers.
    # MockBrain.replies cycles in order across BOTH tasks — so the
    # sequence here is: scout-turn-1 (tool), scout-turn-2 (text),
    # watcher-turn-1 (text).
    brain = MockBrain(replies=[
        [ToolCall(id="c1", name="emit_signal",
                  arguments={"topic": "trending", "strength": 2.0})],
        "Scouted.",
        "Watched.",
    ])
    org.task("scout", target="scout")
    org.task("watch", target="watcher")
    org.run(brain=brain)

    watcher_task = next(t for t in org.tasks if t.target == "watcher")
    trace = org.trace_for(watcher_task.id)
    [entry] = trace.entries
    assert "Active colony signals" in (entry.system or "")
    assert "trending" in (entry.system or "")
