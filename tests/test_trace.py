"""Tests for the Thought Trail — TraceObserver, emit_think_event, org.trace_for."""
import pytest

from ormica import Agent, Ormica
from ormica.arbor import Tree
from ormica.brain import MockBrain, ToolCall, tool
from ormica.observe import (
    THINK_RECORDED,
    EventBus,
    Trace,
    TraceEntry,
    TraceObserver,
    emit_think_event,
)


# --- emit_think_event shape ---------------------------------------------------


def test_emit_think_event_writes_expected_payload():
    bus = EventBus()
    captured = []
    bus.subscribe(type("X", (), {"notify": lambda self, e: captured.append(e)})())

    brain = MockBrain(replies=["hello world"])
    response = brain.think("hi", system="terse")

    emit_think_event(
        bus,
        task_id="t1",
        node_id="n1",
        messages=brain.calls[0],
        system="terse",
        tools=[],
        response=response,
    )

    assert captured[0].type == THINK_RECORDED
    p = captured[0].payload
    assert p["task_id"] == "t1"
    assert p["node_id"] == "n1"
    assert p["response_content"] == "hello world"
    assert p["response_tool_calls"] == []
    assert p["tool_names"] == []
    assert p["tokens_used"] > 0


# --- TraceObserver standalone ------------------------------------------------


def _seed_trace(obs: TraceObserver, bus: EventBus, *, task_id: str, target: str):
    bus.emit(
        "task.started",
        source="runner",
        task_id=task_id,
        target=target,
        description="do thing",
        priority="normal",
    )


def test_trace_observer_captures_full_task_lifecycle():
    obs = TraceObserver()
    bus = EventBus()
    bus.subscribe(obs)

    _seed_trace(obs, bus, task_id="t1", target="sales")

    # Two think calls in the task.
    brain = MockBrain(replies=["partial", "final"])
    response_one = brain.think("first")
    emit_think_event(
        bus, task_id="t1", node_id="n1",
        messages=brain.calls[0], system=None, tools=[], response=response_one,
    )
    response_two = brain.think("second")
    emit_think_event(
        bus, task_id="t1", node_id="n1",
        messages=brain.calls[1], system=None, tools=[], response=response_two,
    )
    bus.emit("task.done", source="runner", task_id="t1", target="sales", tokens_used=5)

    trace = obs.for_task("t1")
    assert isinstance(trace, Trace)
    assert trace.task_id == "t1"
    assert trace.status == "done"
    assert trace.target == "sales"
    assert len(trace.entries) == 2
    assert trace.entries[0].response_content == "partial"
    assert trace.entries[1].response_content == "final"


def test_trace_observer_records_failed_status():
    obs = TraceObserver()
    bus = EventBus()
    bus.subscribe(obs)
    _seed_trace(obs, bus, task_id="t2", target="ghost")
    bus.emit("task.failed", source="runner", task_id="t2", target="ghost", error="boom")
    trace = obs.for_task("t2")
    assert trace.status == "failed"
    assert trace.error == "boom"


def test_trace_observer_ignores_think_for_unknown_task():
    obs = TraceObserver()
    bus = EventBus()
    bus.subscribe(obs)
    brain = MockBrain(replies=["x"])
    emit_think_event(
        bus, task_id="ghost-id", node_id="n1",
        messages=brain.calls if brain.calls else [],
        system=None, tools=[], response=brain.think("hi"),
    )
    # Never went through task.started, so no trace exists.
    assert obs.for_task("ghost-id") is None


# --- End-to-end via Ormica run() ---------------------------------------------


def test_org_run_produces_trace_with_one_entry_per_task():
    org = Ormica("HQ")
    org.spawn("sales", role="sales")
    t = org.task("close deals", dept="sales")

    obs = TraceObserver(store=org.memory)
    org.subscribe(obs)

    org.run(brain=MockBrain(replies=["3 deals booked"]))

    trace = obs.for_task(t.id)
    assert trace is not None
    assert trace.status == "done"
    assert len(trace.entries) == 1
    assert trace.entries[0].response_content == "3 deals booked"


def test_trace_persists_to_mycelium_when_store_given():
    org = Ormica("HQ")
    t = org.task("hello")
    obs = TraceObserver(store=org.memory)
    org.subscribe(obs)

    org.run(brain=MockBrain(replies=["greeting"]))
    entry = org.memory.read(f"traces/{t.id}")
    assert entry is not None
    assert entry.value["status"] == "done"
    assert entry.value["entries"][0]["response_content"] == "greeting"


def test_org_trace_for_reads_from_mycelium():
    org = Ormica("HQ")
    t = org.task("hi")
    obs = TraceObserver(store=org.memory)
    org.subscribe(obs)
    org.run(brain=MockBrain(replies=["yo"]))

    # Drop the observer to prove we read from mycelium not the observer cache.
    org.events.unsubscribe(obs)
    trace = org.trace_for(t.id)
    assert trace is not None
    assert trace.entries[0].response_content == "yo"


def test_org_trace_for_falls_back_to_subscribed_observer():
    """No persistence — but a subscribed TraceObserver has it in-memory."""
    org = Ormica("HQ")
    t = org.task("hi")
    obs = TraceObserver()  # no store
    org.subscribe(obs)
    org.run(brain=MockBrain(replies=["from observer"]))

    trace = org.trace_for(t.id)
    assert trace is not None
    assert trace.entries[0].response_content == "from observer"


def test_org_trace_for_returns_none_when_nothing_recorded():
    org = Ormica("HQ")
    assert org.trace_for("nonexistent") is None


# --- Tool-use trace -----------------------------------------------------------


def test_trace_captures_tool_use_loop():
    org = Ormica("HQ")
    node = org.spawn("worker")

    @tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    brain = MockBrain(replies=[
        [ToolCall(id="c1", name="add", arguments={"a": 1, "b": 2})],
        "result is 3",
    ])
    obs = TraceObserver()
    org.subscribe(obs)

    # Simulate the runner's wiring manually for unit-test scope.
    org.events.emit(
        "task.started",
        source="runner",
        task_id="t-tool",
        target="worker",
        description="add 1+2",
        priority="normal",
    )
    agent = Agent(node, brain)
    agent.events = org.events
    agent.task_id = "t-tool"
    agent.act_with_tools("compute", tools=[add])
    org.events.emit("task.done", source="runner", task_id="t-tool", target="worker", tokens_used=2)

    trace = obs.for_task("t-tool")
    assert len(trace.entries) == 2
    # First entry should have a tool_use; second should have plain text.
    assert trace.entries[0].response_tool_calls
    assert trace.entries[0].response_tool_calls[0]["name"] == "add"
    assert trace.entries[1].response_content == "result is 3"


# --- Failure isolation --------------------------------------------------------


def test_trace_persist_failure_does_not_crash_run():
    """A broken store must not abort the run."""
    class BrokenStore:
        def write(self, *_args, **_kwargs):
            raise RuntimeError("disk full")

    org = Ormica("HQ")
    org.task("hi")
    obs = TraceObserver(store=BrokenStore())
    org.subscribe(obs)

    result = org.run(brain=MockBrain(replies=["ok"]))
    assert result.succeeded == 1
