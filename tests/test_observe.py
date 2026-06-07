"""Tests for the observe module — Event, EventBus, Observer impls, runner hooks."""
import io
from typing import Any

import pytest

from ormica import Ormica
from ormica.brain import AsyncMockBrain, MockBrain
from ormica.observe import (
    RUN_COMPLETED,
    RUN_STARTED,
    TASK_DONE,
    TASK_FAILED,
    TASK_STARTED,
    CollectObserver,
    CounterObserver,
    Event,
    EventBus,
    LogObserver,
    Observer,
)


# --- Event / EventBus core ----------------------------------------------------


def test_emit_returns_populated_event():
    bus = EventBus()
    event = bus.emit("foo.bar", source="test", k=1, msg="hi")
    assert event.type == "foo.bar"
    assert event.source == "test"
    assert event.payload == {"k": 1, "msg": "hi"}
    assert event.timestamp > 0


def test_observers_receive_events_in_subscription_order():
    bus = EventBus()
    seen: list[tuple[str, str]] = []

    class Sink:
        def __init__(self, label: str) -> None:
            self.label = label

        def notify(self, e: Event) -> None:
            seen.append((self.label, e.type))

    bus.subscribe(Sink("a"))
    bus.subscribe(Sink("b"))
    bus.emit("ping")
    assert seen == [("a", "ping"), ("b", "ping")]


def test_unsubscribe_removes_observer():
    bus = EventBus()
    counter = CounterObserver()
    bus.subscribe(counter)
    bus.emit("x")
    bus.unsubscribe(counter)
    bus.emit("x")
    assert counter.get("x") == 1


def test_failing_observer_does_not_block_others():
    bus = EventBus()

    class Boom:
        def notify(self, event: Event) -> None:
            raise RuntimeError("kapow")

    counter = CounterObserver()
    bus.subscribe(Boom())
    bus.subscribe(counter)
    bus.emit("survivor")
    assert counter.get("survivor") == 1


# --- Built-in observers -------------------------------------------------------


def test_counter_observer_tracks_counts_by_type():
    c = CounterObserver()
    c.notify(Event(type="task.done"))
    c.notify(Event(type="task.done"))
    c.notify(Event(type="task.failed"))
    assert c.get("task.done") == 2
    assert c.get("task.failed") == 1
    assert c.get("nope") == 0
    assert c.total() == 3


def test_collect_observer_stores_events_and_filters():
    c = CollectObserver()
    c.notify(Event(type="task.done", payload={"id": "a"}))
    c.notify(Event(type="task.failed", payload={"id": "b"}))
    c.notify(Event(type="task.done", payload={"id": "c"}))
    assert len(c.events) == 3
    assert [e.payload["id"] for e in c.of_type("task.done")] == ["a", "c"]


def test_log_observer_prints_to_stream():
    stream = io.StringIO()
    obs = LogObserver(stream=stream)
    obs.notify(
        Event(type="task.done", source="runner", payload={"task_id": "abc", "target": "sales"})
    )
    text = stream.getvalue()
    assert "task.done" in text
    assert "src=runner" in text
    assert "task_id=abc" in text
    assert "target=sales" in text


def test_observer_protocol_recognises_builtins():
    for obs in (LogObserver(stream=io.StringIO()), CounterObserver(), CollectObserver()):
        assert isinstance(obs, Observer)


# --- ConsoleObserver ----------------------------------------------------------


def test_console_observer_renders_task_started():
    from ormica.observe import ConsoleObserver, TASK_STARTED
    stream = io.StringIO()
    obs = ConsoleObserver(stream=stream)
    obs.notify(Event(
        type=TASK_STARTED,
        source="runner",
        payload={"task_id": "abc12345xyz", "target": "sales", "priority": "high",
                 "description": "scout the area"},
    ))
    text = stream.getvalue()
    assert "» task abc12345 started" in text
    assert "target=sales" in text
    assert "priority=high" in text
    assert "scout the area" in text


def test_console_observer_renders_task_done():
    from ormica.observe import ConsoleObserver, TASK_DONE
    stream = io.StringIO()
    ConsoleObserver(stream=stream).notify(Event(
        type=TASK_DONE,
        source="runner",
        payload={"task_id": "abc12345", "tokens_used": 42},
    ))
    assert "✓ task abc12345 done" in stream.getvalue()
    assert "tokens=42" in stream.getvalue()


def test_console_observer_renders_task_failed():
    from ormica.observe import ConsoleObserver, TASK_FAILED
    stream = io.StringIO()
    ConsoleObserver(stream=stream).notify(Event(
        type=TASK_FAILED,
        source="runner",
        payload={"task_id": "def67890", "error": "RuleViolation: boom"},
    ))
    assert "✗ task def67890 failed" in stream.getvalue()
    assert "RuleViolation" in stream.getvalue()


def test_console_observer_renders_soft_rule():
    from ormica.observe import ConsoleObserver, RULE_SOFT_VIOLATION
    stream = io.StringIO()
    ConsoleObserver(stream=stream).notify(Event(
        type=RULE_SOFT_VIOLATION,
        source="constitution",
        payload={"rule": "prefer_short", "stage": "post", "node": "scout"},
    ))
    text = stream.getvalue()
    assert "⚠ rule.soft fired" in text
    assert "rule=prefer_short" in text


def test_console_observer_skips_run_events_by_default():
    """Run summary lines only render when include_run=True."""
    from ormica.observe import ConsoleObserver, RUN_STARTED, RUN_COMPLETED
    stream = io.StringIO()
    obs = ConsoleObserver(stream=stream)
    for et in (RUN_STARTED, RUN_COMPLETED):
        obs.notify(Event(type=et, source="runner", payload={}))
    assert stream.getvalue() == ""  # silenced


def test_console_observer_renders_run_events_when_opted_in():
    from ormica.observe import ConsoleObserver, RUN_STARTED, RUN_COMPLETED
    stream = io.StringIO()
    obs = ConsoleObserver(stream=stream, include_run=True)
    obs.notify(Event(type=RUN_STARTED, source="runner",
                     payload={"n_tasks": 3, "mode": "sync"}))
    obs.notify(Event(type=RUN_COMPLETED, source="runner",
                     payload={"processed": 3, "succeeded": 2, "failed": 1}))
    text = stream.getvalue()
    assert "▶ run started" in text
    assert "■ run complete" in text
    assert "succeeded=2" in text


# --- Ormica.events integration -----------------------------------------------


def test_org_subscribe_shortcut_wires_into_bus():
    org = Ormica("HQ")
    counter = CounterObserver()
    org.subscribe(counter)
    org.events.emit("custom")
    assert counter.get("custom") == 1


# --- Sync runner emits expected lifecycle events ------------------------------


def test_sync_run_emits_run_and_task_events():
    org = Ormica("HQ")
    org.spawn("sales", role="sales")
    org.task("close deals", dept="sales", priority="high")

    collector = CollectObserver()
    org.subscribe(collector)

    org.run(brain=MockBrain(replies=["3 deals closed"]))

    types = [e.type for e in collector.events]
    # Lifecycle markers fire in order; think.recorded sits between TASK_STARTED and TASK_DONE.
    assert types[0] == RUN_STARTED
    assert types[1] == TASK_STARTED
    assert types[-2] == TASK_DONE
    assert types[-1] == RUN_COMPLETED

    started = collector.of_type(TASK_STARTED)[0]
    assert started.payload["target"] == "sales"
    assert started.payload["priority"] == "high"
    done = collector.of_type(TASK_DONE)[0]
    assert done.payload["target"] == "sales"
    assert done.payload["tokens_used"] > 0


def test_sync_run_emits_task_failed_when_target_unknown():
    org = Ormica("HQ")
    org.task("ghost work", dept="nonexistent")

    collector = CollectObserver()
    org.subscribe(collector)
    org.run(brain=MockBrain(replies=["unused"]))

    types = [e.type for e in collector.events]
    assert TASK_FAILED in types
    assert TASK_DONE not in types
    failed = collector.of_type(TASK_FAILED)[0]
    assert "NodeNotFound" in failed.payload["error"]


def test_sync_run_completed_payload_has_counts():
    org = Ormica("HQ")
    org.task("a")
    org.task("b")
    counter = CounterObserver()
    org.subscribe(counter)
    collector = CollectObserver()
    org.subscribe(collector)

    org.run(brain=MockBrain(replies=["ok"]))

    completed = collector.of_type(RUN_COMPLETED)[0]
    assert completed.payload == {"processed": 2, "succeeded": 2, "failed": 0}
    assert counter.get(TASK_DONE) == 2


# --- Async runner emits the same shape ----------------------------------------


@pytest.mark.asyncio
async def test_async_run_emits_run_and_task_events():
    org = Ormica("HQ")
    org.spawn("sales", role="sales")
    org.task("a", dept="sales", priority="high")
    org.task("b", dept="sales", priority="normal")

    collector = CollectObserver()
    org.subscribe(collector)

    await org.arun(brain=AsyncMockBrain(replies=["ok"]))

    # Two task pairs (started+done) plus run.started/completed.
    types = [e.type for e in collector.events]
    assert types[0] == RUN_STARTED
    assert types[-1] == RUN_COMPLETED
    assert types.count(TASK_STARTED) == 2
    assert types.count(TASK_DONE) == 2

    run_started = collector.of_type(RUN_STARTED)[0]
    assert run_started.payload["mode"] == "async"
    assert run_started.payload["n_tasks"] == 2


# --- Side-effect isolation / robustness ---------------------------------------


def test_event_payload_keys_carry_through_kwargs():
    bus = EventBus()
    collected: list[Any] = []
    bus.subscribe(type("X", (), {"notify": lambda self, e: collected.append(e.payload)})())
    bus.emit("x", source="runner", a=1, b="two", c=[1, 2])
    assert collected[0] == {"a": 1, "b": "two", "c": [1, 2]}


def test_log_observer_default_stream_is_stderr_writeable():
    """Smoke: constructing without args is fine; we don't assert on system stderr."""
    obs = LogObserver()
    assert obs.stream is not None
