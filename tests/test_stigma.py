"""Tests for the stigma module — pheromone trails, decay, reinforcement, selection."""
import math

import pytest

from ormica.arbor import Tree
from ormica.mycelium import Mycelium
from ormica.stigma import Signal, Stigma


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _make(half_life: float = 10.0, floor: float = 0.01) -> tuple[Stigma, FakeClock]:
    clock = FakeClock()
    mem = Mycelium(clock=clock)
    return Stigma(mem, half_life=half_life, floor=floor), clock


def test_emit_creates_signal_at_given_strength():
    stig, _ = _make()
    sig = stig.emit("path_to_food", strength=2.0, by="ant-1")

    assert sig.topic == "path_to_food"
    assert sig.strength == 2.0
    assert sig.sources == {"ant-1"}

    sensed = stig.sense("path_to_food")
    assert sensed is not None
    assert sensed.strength == pytest.approx(2.0)


def test_emit_overwrites_existing_trail():
    stig, _ = _make()
    stig.emit("a", strength=5.0, by="ant-1")
    stig.emit("a", strength=1.0, by="ant-2")

    sensed = stig.sense("a")
    assert sensed.strength == pytest.approx(1.0)
    assert sensed.sources == {"ant-2"}  # emit replaces — not accumulates


def test_reinforce_on_empty_creates_trail():
    stig, _ = _make()
    sig = stig.reinforce("new_trail", amount=3.0, by="ant-7")

    assert sig.strength == 3.0
    assert sig.sources == {"ant-7"}


def test_reinforce_accumulates_strength_and_sources():
    stig, _ = _make()
    stig.emit("trail", strength=1.0, by="ant-1")
    stig.reinforce("trail", amount=1.0, by="ant-2")
    stig.reinforce("trail", amount=1.0, by="ant-3")

    sensed = stig.sense("trail")
    assert sensed.strength == pytest.approx(3.0)
    assert sensed.sources == {"ant-1", "ant-2", "ant-3"}


def test_strength_halves_after_one_half_life():
    stig, clock = _make(half_life=10.0)
    stig.emit("trail", strength=8.0)

    clock.advance(10)
    sensed = stig.sense("trail")
    assert sensed.strength == pytest.approx(4.0)

    clock.advance(10)
    sensed = stig.sense("trail")
    assert sensed.strength == pytest.approx(2.0)


def test_reinforcement_adds_to_decayed_strength_not_stored_strength():
    stig, clock = _make(half_life=10.0)
    stig.emit("trail", strength=4.0)
    clock.advance(10)  # decays to 2.0
    stig.reinforce("trail", amount=1.0)

    sensed = stig.sense("trail")
    # Just reinforced, no further decay.
    assert sensed.strength == pytest.approx(3.0)


def test_sense_returns_none_when_signal_decays_below_floor():
    stig, clock = _make(half_life=1.0, floor=0.1)
    stig.emit("faint", strength=1.0)
    clock.advance(100)  # 1.0 * 0.5**100 ≪ floor

    assert stig.sense("faint") is None


def test_sense_returns_none_for_missing_topic():
    stig, _ = _make()
    assert stig.sense("nope") is None


def test_trails_sorted_by_strength_descending():
    stig, _ = _make()
    stig.emit("weak", strength=0.5)
    stig.emit("strong", strength=5.0)
    stig.emit("mid", strength=2.0)

    topics = [t.topic for t in stig.trails()]
    assert topics == ["strong", "mid", "weak"]


def test_top_returns_n_strongest():
    stig, _ = _make()
    for i, topic in enumerate(["a", "b", "c", "d"]):
        stig.emit(topic, strength=float(i + 1))

    top2 = stig.top(2)
    assert [s.topic for s in top2] == ["d", "c"]


def test_evaporate_removes_below_floor_signals():
    stig, clock = _make(half_life=1.0, floor=0.1)
    stig.emit("keep", strength=100.0)
    stig.emit("drop", strength=0.5)

    clock.advance(10)  # 0.5 * 0.5**10 → very small; 100 * 0.5**10 ≈ 0.098 — also below 0.1
    # Re-emit to keep "keep" alive
    stig.emit("keep", strength=100.0)

    dropped = stig.evaporate()
    assert dropped == 1
    assert stig.sense("keep") is not None
    assert stig.sense("drop") is None


def test_stigma_uses_mycelium_under_key_prefix():
    mem = Mycelium()
    stig = Stigma(mem)
    stig.emit("hello", strength=1.0)

    entry = mem.read("stigma/hello")
    assert entry is not None
    assert entry.value["strength"] == 1.0
    assert entry.meta == {"kind": "stigma.signal", "topic": "hello"}


def test_stigma_signals_dont_collide_with_plain_memory():
    mem = Mycelium()
    stig = Stigma(mem)
    mem.write("notes", "ignore this")  # non-signal entry
    stig.emit("trail", strength=1.0)

    trails = stig.trails()
    assert [t.topic for t in trails] == ["trail"]  # plain entry ignored


def test_nodes_can_emit_via_their_id():
    """Integration: a node from arbor leaves a signal in stigma."""
    tree = Tree("HQ")
    scout = tree.spawn(tree.root, "scout")
    mem = Mycelium()
    # Neutralise half-life decay — this test verifies wiring, not decay.
    # See 6f2699a for the same pattern applied to test_emit_and_sense_use_stigma_when_wired.
    stig = Stigma(mem, half_life=1e9)

    stig.emit("food_sighted", strength=1.0, by=scout.id)
    stig.reinforce("food_sighted", amount=0.5, by=scout.id)

    sensed = stig.sense("food_sighted")
    assert sensed.sources == {scout.id}
    assert sensed.strength == pytest.approx(1.5)


def test_invalid_construction_rejected():
    mem = Mycelium()
    with pytest.raises(ValueError):
        Stigma(mem, half_life=0)
    with pytest.raises(ValueError):
        Stigma(mem, floor=-0.1)


def test_signal_strength_at_is_correct_pure_function():
    # Direct test of the decay math without going through Stigma.
    s = Signal(topic="x", strength=1.0, last_touched=0.0)
    assert s.strength_at(0.0, half_life=10.0) == pytest.approx(1.0)
    assert s.strength_at(10.0, half_life=10.0) == pytest.approx(0.5)
    assert s.strength_at(20.0, half_life=10.0) == pytest.approx(0.25)
    # Clamps elapsed at zero (no anti-decay if clock goes backwards).
    assert s.strength_at(-5.0, half_life=10.0) == pytest.approx(1.0)
    # Math sanity: 30s half-life, 30s elapsed → exactly half.
    s2 = Signal(topic="x", strength=8.0, last_touched=100.0)
    assert s2.strength_at(130.0, half_life=30.0) == pytest.approx(4.0)
    # General check matches the formula.
    expected = 8.0 * math.pow(0.5, 45 / 30)
    assert s2.strength_at(145.0, half_life=30.0) == pytest.approx(expected)
