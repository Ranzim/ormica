"""TraceEntry / Trace / TraceObserver — the Thought Trail.

Captures the full reasoning trail for one task: each ``Brain.think`` call
that happened on the way to the final answer, with its messages,
tool-use blocks, and tool results.

Use:
    from ormica.observe import TraceObserver

    trace_obs = TraceObserver(store=org.memory)
    org.subscribe(trace_obs)
    org.run(brain=...)
    trail = trace_obs.for_task(task.id)        # in-memory access
    trail = org.trace_for(task.id)             # mycelium-backed access
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .event import (
    RUN_COMPLETED,
    TASK_DONE,
    TASK_FAILED,
    TASK_STARTED,
    Event,
)

THINK_RECORDED = "think.recorded"


@dataclass
class TraceEntry:
    """One Brain.think call within a task: prompt, tools, response."""

    timestamp: float
    messages: list  # serializable list of {"role", "content", "tool_calls"?, "tool_call_id"?}
    system: Optional[str]
    tool_names: list[str]
    response_content: str
    response_tool_calls: list  # list of {"id", "name", "arguments"}
    tokens_used: int
    finish_reason: str = ""


@dataclass
class Trace:
    """The full Thought Trail for a single task."""

    task_id: str
    node_id: str = ""
    target: str = ""
    description: str = ""
    started_at: float = 0.0
    ended_at: float = 0.0
    status: str = "running"  # running | done | failed
    result: Optional[str] = None
    error: Optional[str] = None
    entries: list[TraceEntry] = field(default_factory=list)


def _msg_to_dict(m: Any) -> dict:
    base = {"role": m.role, "content": m.content}
    if getattr(m, "tool_calls", None):
        base["tool_calls"] = [
            {"id": c.id, "name": c.name, "arguments": c.arguments}
            for c in m.tool_calls
        ]
    if getattr(m, "tool_call_id", ""):
        base["tool_call_id"] = m.tool_call_id
    return base


def _toolcall_to_dict(c: Any) -> dict:
    return {"id": c.id, "name": c.name, "arguments": c.arguments}


class TraceObserver:
    """Observer that aggregates per-task think calls into a :class:`Trace`.

    Subscribes to runner lifecycle events (``task.started`` / ``task.done`` /
    ``task.failed``) and per-think events (``think.recorded`` emitted by
    Agent / AsyncAgent when given an EventBus). Maintains an in-memory
    map of completed traces; if ``store`` is provided, also persists each
    finished trace into mycelium under ``traces/{task_id}``.
    """

    def __init__(self, store: Any = None) -> None:
        self._open: dict[str, Trace] = {}
        self._done: dict[str, Trace] = {}
        self.store = store

    # --- Observer protocol ---

    def notify(self, event: Event) -> None:
        if event.type == TASK_STARTED:
            self._on_task_started(event)
        elif event.type == THINK_RECORDED:
            self._on_think(event)
        elif event.type == TASK_DONE:
            self._on_task_finished(event, status="done")
        elif event.type == TASK_FAILED:
            self._on_task_finished(event, status="failed")
        elif event.type == RUN_COMPLETED:
            pass  # nothing to do; traces already finalized per task

    # --- query API ---

    def for_task(self, task_id: str) -> Optional[Trace]:
        return self._done.get(task_id) or self._open.get(task_id)

    def all(self) -> list[Trace]:
        return list(self._done.values())

    # --- handlers ---

    def _on_task_started(self, event: Event) -> None:
        task_id = event.payload.get("task_id", "")
        if not task_id:
            return
        self._open[task_id] = Trace(
            task_id=task_id,
            target=event.payload.get("target", ""),
            description=event.payload.get("description", ""),
            started_at=event.timestamp,
        )

    def _on_think(self, event: Event) -> None:
        task_id = event.payload.get("task_id", "")
        if not task_id or task_id not in self._open:
            return
        trace = self._open[task_id]
        if not trace.node_id:
            trace.node_id = event.payload.get("node_id", "")
        trace.entries.append(
            TraceEntry(
                timestamp=event.timestamp,
                messages=event.payload.get("messages", []),
                system=event.payload.get("system"),
                tool_names=event.payload.get("tool_names", []),
                response_content=event.payload.get("response_content", ""),
                response_tool_calls=event.payload.get("response_tool_calls", []),
                tokens_used=event.payload.get("tokens_used", 0),
                finish_reason=event.payload.get("finish_reason", ""),
            )
        )

    def _on_task_finished(self, event: Event, *, status: str) -> None:
        task_id = event.payload.get("task_id", "")
        if not task_id or task_id not in self._open:
            return
        trace = self._open.pop(task_id)
        trace.ended_at = event.timestamp
        trace.status = status
        if status == "done":
            # task.done payload exposes tokens but not result text; the runner
            # writes the full task record to mycelium separately. We keep the
            # trace itself lean — full text lives in the per-entry response_content.
            pass
        elif status == "failed":
            trace.error = event.payload.get("error", "")
        self._done[task_id] = trace

        if self.store is not None:
            self._persist(trace)

    def _persist(self, trace: Trace) -> None:
        from dataclasses import asdict

        try:
            self.store.write(
                f"traces/{trace.task_id}",
                asdict(trace),
                author=trace.node_id or None,
            )
        except Exception:  # noqa: BLE001 — observability must not crash the run
            pass


def emit_think_event(
    events_bus: Any,
    *,
    task_id: str,
    node_id: str,
    messages: list,
    system: Optional[str],
    tools: list,
    response: Any,
) -> None:
    """Emit a ``think.recorded`` event onto ``events_bus``.

    Called by Agent / AsyncAgent right after a Brain.think call. Empty
    ``task_id`` is allowed — the observer drops events that aren't
    tied to a started task.
    """
    events_bus.emit(
        THINK_RECORDED,
        source="agent",
        task_id=task_id,
        node_id=node_id,
        messages=[_msg_to_dict(m) for m in messages],
        system=system,
        tool_names=[t.name for t in (tools or [])],
        response_content=response.content,
        response_tool_calls=[_toolcall_to_dict(c) for c in response.tool_calls],
        tokens_used=response.tokens_used,
        finish_reason=response.finish_reason,
    )
