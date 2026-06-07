"""Tests for yaml-declared static emits — the write-side complement to sense_prefixes."""
from __future__ import annotations

from pathlib import Path

import pytest

from ormica import Ormica
from ormica.brain import MockBrain
from ormica.colony import load_colony


# --- loader: parse emits: into (topic, strength) tuples ----------------------


def _load(tmp_path: Path, body: str):
    yml = tmp_path / "c.yaml"
    yml.write_text(body)
    return load_colony(yml)


def test_bare_string_emit_defaults_to_strength_0_5(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    emits:
      - "trending:weekly-shifts"
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    assert node.meta["emits"] == [["trending:weekly-shifts", 0.5]]


def test_explicit_topic_strength_mapping(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    emits:
      - {topic: "ship-pressure", strength: 1.5}
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    assert node.meta["emits"] == [["ship-pressure", 1.5]]


def test_single_key_shorthand(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    emits:
      - {trending: 2.0}
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    assert node.meta["emits"] == [["trending", 2.0]]


def test_single_key_null_value_defaults_to_default_strength(tmp_path: Path):
    """`trending:` parses to {trending: None} — strength defaults to 0.5."""
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    emits:
      - trending:
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    assert node.meta["emits"] == [["trending", 0.5]]


def test_mixed_forms_in_one_list(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    emits:
      - "a:plain"
      - {topic: "b:explicit", strength: 1.0}
      - {c: 2.0}
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    assert node.meta["emits"] == [
        ["a:plain", 0.5],
        ["b:explicit", 1.0],
        ["c", 2.0],
    ]


def test_no_emits_field_means_no_meta_entry(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: e
    role: e
""")
    org = Ormica("X")
    [node] = cls().plant(org)
    assert "emits" not in node.meta


# --- error paths --------------------------------------------------------------


def test_emits_must_be_list(tmp_path: Path):
    with pytest.raises(ValueError, match="'emits' must be a list"):
        _load(tmp_path, """
name: x
templates:
  - name: e
    role: e
    emits: "not a list"
""")


def test_empty_topic_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="emit topic cannot be empty"):
        _load(tmp_path, """
name: x
templates:
  - name: e
    role: e
    emits:
      - ""
""")


def test_non_numeric_strength_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="must be a number"):
        _load(tmp_path, """
name: x
templates:
  - name: e
    role: e
    emits:
      - {topic: "ok", strength: "very strong"}
""")


def test_zero_or_negative_strength_rejected(tmp_path: Path):
    """Stigma.reinforce on zero strength would be a no-op silently; reject up front."""
    with pytest.raises(ValueError, match="must be > 0"):
        _load(tmp_path, """
name: x
templates:
  - name: e
    role: e
    emits:
      - {topic: "ok", strength: 0}
""")


# --- runtime: emits reinforced on task finalize ------------------------------


def test_runner_reinforces_declared_emits(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    emits:
      - "trending:hot-topic"
      - {topic: "ship-pressure", strength: 1.5}
""")
    org = Ormica("X", max_depth=4)
    cls().plant(org)

    # Task targets the emitter. After completion, trails should appear.
    org.task("do something", target="emitter")
    org.run(brain=MockBrain(replies=["ok"]))

    topics = {s.topic: s.strength for s in org.signals.trails()}
    # Default strength 0.5 — slight decay possible since signals_half_life=60s.
    assert "trending:hot-topic" in topics
    assert topics["trending:hot-topic"] == pytest.approx(0.5, abs=0.01)
    assert topics["ship-pressure"] == pytest.approx(1.5, abs=0.02)


def test_repeated_runs_reinforce_existing_trail(tmp_path: Path):
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    emits:
      - {topic: "growing", strength: 1.0}
""")
    org = Ormica("X", max_depth=4, signals_half_life=3600)  # long half-life, accumulation should win
    cls().plant(org)

    for _ in range(3):
        org.task("do something", target="emitter")
    org.run(brain=MockBrain(replies=["ok", "ok", "ok"]))

    topics = {s.topic: s.strength for s in org.signals.trails()}
    # Three reinforcements of 1.0 each should be ~3.0 (with negligible decay over the test).
    assert topics["growing"] == pytest.approx(3.0, abs=0.1)


def test_emit_failure_does_not_fail_the_task(tmp_path: Path, monkeypatch):
    """Defensive: a stigma write failure in _maybe_auto_emit must not break the task."""
    cls = _load(tmp_path, """
name: x
templates:
  - name: emitter
    role: e
    emits:
      - "fine"
""")
    org = Ormica("X", max_depth=4)
    cls().plant(org)

    def boom(*a, **kw):
        raise RuntimeError("stigma is broken")
    monkeypatch.setattr(org.signals, "reinforce", boom)

    org.task("do something", target="emitter")
    result = org.run(brain=MockBrain(replies=["ok"]))
    assert result.succeeded == 1
    assert result.failed == 0


# --- end-to-end: emit + sense compose -----------------------------------------


def test_emit_on_one_node_is_sensed_by_another(tmp_path: Path):
    """The whole point: a node's declared emits land in another node's prompt."""
    from ormica.observe import TraceObserver

    cls = _load(tmp_path, """
name: chain
templates:
  - name: emitter
    role: emitter
    task: Mark progress
    emits:
      - {topic: "milestone:phase-1", strength: 2.0}
  - name: watcher
    role: watcher
    task: React to milestones
    sense_prefixes: ["milestone:"]
""")
    org = Ormica("X", max_depth=4)
    cls().plant(org)
    org.subscribe(TraceObserver(store=org.memory))

    # Emitter runs first, lays down milestone:phase-1.
    org.task("step done", target="emitter")
    # Then watcher runs — should see the milestone in its system prompt.
    org.task("look around", target="watcher")
    org.run(brain=MockBrain(replies=["ok", "ok"]))

    watcher_task = next(t for t in org.tasks if t.target == "watcher")
    trace = org.trace_for(watcher_task.id)
    [entry] = trace.entries
    assert "Active colony signals" in (entry.system or "")
    assert "milestone:phase-1" in (entry.system or "")
