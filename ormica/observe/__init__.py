"""
observe — events, observers, and the bus.

Tasks and runners emit events ("task.started", "task.done", "task.failed",
"run.started", "run.completed"). Observers (LogObserver, CounterObserver,
CollectObserver, or your own) consume them through the org's EventBus.

Biological metaphor: the nervous system — signals from anywhere, sensed everywhere.
"""

from .bus import EventBus
from .event import (
    RUN_COMPLETED,
    RUN_STARTED,
    TASK_DONE,
    TASK_FAILED,
    TASK_STARTED,
    Event,
)
from .observer import CollectObserver, CounterObserver, LogObserver, Observer
from .trace import THINK_RECORDED, Trace, TraceEntry, TraceObserver, emit_think_event

__all__ = [
    "CollectObserver",
    "CounterObserver",
    "Event",
    "EventBus",
    "LogObserver",
    "Observer",
    "RUN_COMPLETED",
    "RUN_STARTED",
    "TASK_DONE",
    "TASK_FAILED",
    "TASK_STARTED",
    "THINK_RECORDED",
    "Trace",
    "TraceEntry",
    "TraceObserver",
    "emit_think_event",
]
