"""Tests for typed artifacts flowing between tasks (Task.produces / .artifact)."""
import json

import pytest

from ormica import ArtifactType, Ormica, Task
from ormica.brain import AsyncMockBrain, MockBrain
from ormica.runtime import _record_task

Estimate = ArtifactType("estimate", {"cost": float, "days": int})


# --- capture: a task with produces= yields a typed artifact -------------------


def test_task_captures_declared_artifact():
    org = Ormica("Acme")
    org.task('{"cost": 12.5, "days": 3}', produces=Estimate)
    org.run(brain=MockBrain(reply_fn=lambda m: m[-1].content))

    task = org.tasks[0]
    assert task.status == "done"
    assert task.artifact is not None
    assert task.artifact.kind == "estimate"
    assert task.artifact.get("days") == 3


def test_task_without_produces_has_no_artifact():
    org = Ormica("Acme")
    org.task("just talk")
    org.run(brain=MockBrain(replies=["hello"]))
    assert org.tasks[0].result == "hello"
    assert org.tasks[0].artifact is None


def test_malformed_typed_output_fails_the_task():
    org = Ormica("Acme")
    org.task("estimate", produces=Estimate)
    # missing 'days' -> validation failure at the task boundary
    org.run(brain=MockBrain(replies=['{"cost": 1.0}']))
    task = org.tasks[0]
    assert task.status == "failed"
    assert "missing required field 'days'" in task.error


# --- persistence: artifact survives the tasks/{id} record ---------------------


def test_artifact_round_trips_through_task_record():
    org = Ormica("Acme")
    org.task('{"cost": 5.0, "days": 1}', produces=Estimate)
    org.run(brain=MockBrain(reply_fn=lambda m: m[-1].content))

    # re-record and reload from mycelium
    _record_task(org, org.tasks[0], org.root)
    reloaded = org.load_tasks()[0]
    assert reloaded.artifact is not None
    assert reloaded.artifact.get("cost") == 5.0
    assert reloaded.artifact.kind == "estimate"


# --- flow: DAG dependents receive structured input ----------------------------


@pytest.mark.asyncio
async def test_dependent_receives_structured_artifact():
    org = Ormica("Acme")
    org._tasks = [
        Task(description="estimate the work", id="a", produces=Estimate),
        Task(description="write a summary", id="b", depends_on=["a"]),
    ]
    captured = {}

    async def reply(messages):
        text = messages[-1].content
        if "write a summary" in text and "prerequisite" in text:
            captured["b"] = text
            return "summary done"
        return '{"cost": 20.0, "days": 4}'  # task a's typed output

    await org.arun_dag(brain=AsyncMockBrain(reply_fn=reply))

    assert org._tasks[0].artifact.get("days") == 4
    # b saw a's artifact as labeled JSON, not a bare blob of prose.
    assert "(estimate)" in captured["b"]
    assert '"cost": 20.0' in captured["b"]
    assert '"days": 4' in captured["b"]
    # the injected JSON is valid and parseable by the consumer
    block = captured["b"].split("(estimate)\n", 1)[1]
    payload = json.loads(block.split("\n\nYour task", 1)[0])
    assert payload == {"cost": 20.0, "days": 4}


@pytest.mark.asyncio
async def test_untyped_dependency_still_flows_as_text():
    # a task without produces= keeps the original text-injection behavior.
    org = Ormica("Acme")
    org._tasks = [
        Task(description="compute A", id="a"),
        Task(description="use A", id="b", depends_on=["a"]),
    ]
    captured = {}

    async def reply(messages):
        text = messages[-1].content
        if "use A" in text and "prerequisite" in text:
            captured["b"] = text
            return "ok"
        return "A=42"

    await org.arun_dag(brain=AsyncMockBrain(reply_fn=reply))
    assert "A=42" in captured["b"]
    assert "(estimate)" not in captured["b"]
