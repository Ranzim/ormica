"""
observe — events, observers, and the bus.

Tasks and runners emit events ("task.started", "task.done", "task.failed",
"run.started", "run.completed"). Observers (LogObserver, CounterObserver,
CollectObserver, or your own) consume them through the org's EventBus.

Biological metaphor: the nervous system — signals from anywhere, sensed everywhere.
"""

from .bus import EventBus
from .event import (
    RULE_SOFT_VIOLATION,
    RUN_COMPLETED,
    RUN_STARTED,
    TASK_DONE,
    TASK_FAILED,
    TASK_STARTED,
    Event,
)
from .observer import (
    CollectObserver,
    ConsoleObserver,
    CounterObserver,
    LogObserver,
    Observer,
)
from .export import (
    trace_to_dict,
    trace_to_json,
    traces_to_csv_detail,
    traces_to_csv_summary,
    traces_to_jsonl,
)
from .trace import THINK_RECORDED, Trace, TraceEntry, TraceObserver, emit_think_event

__all__ = [
    "CollectObserver",
    "ConsoleObserver",
    "CounterObserver",
    "Event",
    "EventBus",
    "LogObserver",
    "Observer",
    "RULE_SOFT_VIOLATION",
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
    "trace_to_dict",
    "trace_to_json",
    "traces_to_csv_detail",
    "traces_to_csv_summary",
    "traces_to_jsonl",
]
