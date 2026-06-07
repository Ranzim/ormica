"""Tests for Agent.sense_prefixes — read-side stigmergy.

These tests cover the pipe end-to-end:
  - Agent kwarg + node.meta fallback
  - Filtering by topic prefix
  - top_n_sensed cap
  - Composition with explicit system_prompt + role + task
  - Colony yaml declarations land on node.meta
  - TaskRunner picks up the meta and threads it through to the agent
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ormica import Ormica
from ormica.agent import Agent
from ormica.brain import MockBrain
from ormica.colony import load_colony


# --- unit: Agent ---------------------------------------------------------------


def _org_with_signals():
    org = Ormica("S", max_depth=4)
    leaf = org.spawn("leaf", role="worker")
    org.signals.emit("topic:alpha", strength=2.0, by=leaf.id)
    org.signals.emit("topic:beta",  strength=1.0, by=leaf.id)
    org.signals.emit("other:gamma", strength=5.0, by=leaf.id)
    return org, leaf


def test_no_sense_prefixes_means_no_sensed_block():
    org, leaf = _org_with_signals()
    agent = Agent(leaf, MockBrain(replies=["ok"]), signals=org.signals)
    sys = agent._compose_system()
    assert "Active colony signals" not in (sys or "")


def test_explicit_sense_prefixes_injects_matching_trails():
    org, leaf = _org_with_signals()
    agent = Agent(
        leaf,
        MockBrain(replies=["ok"]),
        signals=org.signals,
        sense_prefixes=("topic:",),
    )
    sys = agent._compose_system() or ""
    assert "Active colony signals" in sys
    # topic:* trails present, other:* excluded.
    assert "topic:alpha" in sys
    assert "topic:beta" in sys
    assert "other:gamma" not in sys


def test_node_meta_sense_prefixes_is_fallback_when_kwarg_empty():
    org, leaf = _org_with_signals()
    leaf.meta["sense_prefixes"] = ["topic:"]
    agent = Agent(leaf, MockBrain(replies=["ok"]), signals=org.signals)
    sys = agent._compose_system() or ""
    assert "topic:alpha" in sys


def test_explicit_kwarg_wins_over_meta():
    org, leaf = _org_with_signals()
    leaf.meta["sense_prefixes"] = ["topic:"]
    agent = Agent(
        leaf,
        MockBrain(replies=["ok"]),
        signals=org.signals,
        sense_prefixes=("other:",),
    )
    sys = agent._compose_system() or ""
    assert "other:gamma" in sys
    assert "topic:alpha" not in sys


def test_top_n_caps_the_sensed_block():
    org = Ormica("S")
    leaf = org.spawn("leaf")
    for i in range(10):
        org.signals.emit(f"topic:item-{i}", strength=float(10 - i), by=leaf.id)
    agent = Agent(
        leaf,
        MockBrain(replies=["ok"]),
        signals=org.signals,
        sense_prefixes=("topic:",),
        top_n_sensed=3,
    )
    sys = agent._compose_system() or ""
    lines = [ln for ln in sys.splitlines() if ln.startswith("  - ")]
    assert len(lines) == 3


def test_no_matching_trails_means_no_block():
    org = Ormica("S")
    leaf = org.spawn("leaf")
    org.signals.emit("topic:something", strength=1.0, by=leaf.id)
    agent = Agent(
        leaf,
        MockBrain(replies=["ok"]),
        signals=org.signals,
        sense_prefixes=("nope:",),  # no matches
    )
    sys = agent._compose_system() or ""
    assert "Active colony signals" not in sys


def test_signals_none_means_no_block_even_with_prefixes():
    """Agent without a Stigma cannot sense — defensive against partial wiring."""
    org = Ormica("S")
    leaf = org.spawn("leaf")
    agent = Agent(
        leaf,
        MockBrain(replies=["ok"]),
        signals=None,
        sense_prefixes=("topic:",),
    )
    sys = agent._compose_system()
    # No signals + no role/task/system_prompt → None (cheap-skip path).
    assert sys is None or "Active colony signals" not in sys


# --- integration: colony yaml -------------------------------------------------


def test_yaml_sense_prefixes_lands_on_node_meta(tmp_path: Path):
    yml = tmp_path / "c.yaml"
    yml.write_text("""
name: sensing_demo
templates:
  - name: watcher
    role: watcher
    sense_prefixes: [topic:, activity:]
""")
    cls = load_colony(yml)
    org = Ormica("X")
    [watcher] = cls().plant(org)
    assert watcher.meta["sense_prefixes"] == ["topic:", "activity:"]


def test_yaml_sense_prefixes_accepts_quoted_string(tmp_path: Path):
    """Shorthand: a single prefix can be a quoted string. (Bare trailing
    colons are YAML scanner errors, so quoting is required for the
    single-value form.)"""
    yml = tmp_path / "c.yaml"
    yml.write_text("""
name: shorthand
templates:
  - name: x
    role: x
    sense_prefixes: "topic:"
""")
    cls = load_colony(yml)
    org = Ormica("X")
    [x] = cls().plant(org)
    assert x.meta["sense_prefixes"] == ["topic:"]


def test_yaml_sense_prefixes_bad_type_errors(tmp_path: Path):
    yml = tmp_path / "c.yaml"
    yml.write_text("""
name: bad
templates:
  - name: x
    role: x
    sense_prefixes: 42
""")
    with pytest.raises(ValueError, match="sense_prefixes"):
        load_colony(yml)


# --- end-to-end: TaskRunner threads it through --------------------------------


def test_runner_picks_up_node_meta_sense_prefixes(tmp_path: Path):
    """A node planted with sense_prefixes: produces a system prompt with
    the sensed block when run through the real TaskRunner."""
    from ormica.brain import MockBrain
    from ormica.observe import TraceObserver

    yml = tmp_path / "c.yaml"
    yml.write_text("""
name: end_to_end
templates:
  - name: looker
    role: looker
    task: Watch what's busy
    sense_prefixes: [topic:]
""")
    cls = load_colony(yml)
    org = Ormica("X", max_depth=4)
    cls().plant(org)
    org.signals.emit("topic:hot", strength=3.0, by=org.find("looker").id)
    org.subscribe(TraceObserver(store=org.memory))

    org.task("Tell me what's hot", target="looker")
    org.run(brain=MockBrain(replies=["ok"]))

    trace = org.trace_for(org.tasks[0].id)
    assert trace.status == "done"
    [entry] = trace.entries
    assert "Active colony signals" in (entry.system or "")
    assert "topic:hot" in (entry.system or "")
