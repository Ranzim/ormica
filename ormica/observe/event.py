"""Event — the unit of observability."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import time


# Canonical event types — runners emit these. Strings rather than an enum so
# observers can match on prefix (``task.*``) and so callers can introduce new
# types without changing this module.
RUN_STARTED = "run.started"
RUN_COMPLETED = "run.completed"
TASK_STARTED = "task.started"
TASK_DONE = "task.done"
TASK_FAILED = "task.failed"
RULE_SOFT_VIOLATION = "rule.soft_violation"


@dataclass
class Event:
    """A single observable moment.

    ``type`` is a dotted string like ``"task.done"``. ``source`` names
    the emitter (``"runner"``, ``"tree"``, ``"stigma"``); ``payload`` is
    free-form structured data.
    """

    type: str
    timestamp: float = field(default_factory=time)
    source: str = ""
    payload: dict = field(default_factory=dict)
