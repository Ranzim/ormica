"""Tests for parallel, DAG-aware execution (AsyncDagRunner + planner deps)."""
import asyncio
import json

import pytest

from ormica import Ormica, Planner, Task
from ormica.brain import AsyncMockBrain, MockBrain
from ormica.runtime import _detect_cycle


# --- cycle detection ----------------------------------------------------------


def test_detect_cycle():
    _detect_cycle({"a": [], "b": ["a"]})  # ok, no raise
    with pytest.raises(ValueError, match="cycle"):
        _detect_cycle({"a": ["b"], "b": ["a"]})


# --- planner produces a real DAG ----------------------------------------------


def test_planner_to_tasks_sets_dependencies():
    reply = json.dumps(
        {
            "steps": [
                {"description": "build"},
                {"description": "test", "depends_on": [1]},
                {"description": "deploy", "depends_on": [2]},
            ]
        }
    )
    plan = Planner(MockBrain(replies=[reply])).plan("ship")
    tasks = {t.description: t for t in plan.to_tasks()}
    assert tasks["build"].depends_on == []
    assert tasks["test"].depends_on == [tasks["build"].id]
    assert tasks["deploy"].depends_on == [tasks["test"].id]


def test_dependency_on_decomposed_step_expands_to_its_leaves():
    # Top: A, then B depends on A. A decomposes into A1, A2.
    brain = MockBrain(
        replies=[
            json.dumps({"steps": [{"description": "A"},
                                  {"description": "B", "depends_on": [1]}]}),
            json.dumps({"steps": [{"description": "A1"}, {"description": "A2"}]}),
            json.dumps({"steps": [{"description": "B itself"}]}),  # B is atomic
        ]
    )
    plan = Planner(brain).plan("goal", max_depth=2)
    tasks = {t.description: t for t in plan.to_tasks()}
    a1, a2, b = tasks["A1"], tasks["A2"], tasks["B"]
    # B must wait on both leaves of A.
    assert set(b.depends_on) == {a1.id, a2.id}


# --- DAG execution: ordering + parallelism ------------------------------------


def _dag_org():
    org = Ormica("Acme")
    return org


@pytest.mark.asyncio
async def test_dependencies_run_after_prerequisites():
    org = _dag_org()
    a = Task(description="A", id="a")
    b = Task(description="B", id="b", depends_on=["a"])
    org._tasks = [a, b]

    order: list[str] = []

    async def record(_messages):
        # capture completion order via on_task_done instead; here just reply
        return "ok"

    brain = AsyncMockBrain(reply_fn=record)
    await org.arun_dag(brain=brain, on_task_done=lambda t: order.append(t.id))
    assert order == ["a", "b"]  # b only after a


@pytest.mark.asyncio
async def test_independent_tasks_run_concurrently():
    org = _dag_org()
    org._tasks = [Task(description=f"t{i}", id=f"t{i}") for i in range(4)]

    active = {"now": 0, "max": 0}

    async def slow(_messages):
        active["now"] += 1
        active["max"] = max(active["max"], active["now"])
        await asyncio.sleep(0.02)
        active["now"] -= 1
        return "done"

    brain = AsyncMockBrain(reply_fn=slow)
    result = await org.arun_dag(brain=brain, concurrency=4)
    assert result.succeeded == 4
    assert active["max"] >= 2  # genuinely ran in parallel


@pytest.mark.asyncio
async def test_diamond_dag_runs_middle_pair_in_parallel():
    # a -> {b, c} -> d
    org = _dag_org()
    org._tasks = [
        Task(description="a", id="a"),
        Task(description="b", id="b", depends_on=["a"]),
        Task(description="c", id="c", depends_on=["a"]),
        Task(description="d", id="d", depends_on=["b", "c"]),
    ]
    done_order: list[str] = []
    active = {"now": 0, "max": 0}

    async def work(_messages):
        active["now"] += 1
        active["max"] = max(active["max"], active["now"])
        await asyncio.sleep(0.01)
        active["now"] -= 1
        return "ok"

    await org.arun_dag(
        brain=AsyncMockBrain(reply_fn=work),
        concurrency=4,
        on_task_done=lambda t: done_order.append(t.id),
    )
    assert done_order[0] == "a"
    assert done_order[-1] == "d"
    assert set(done_order[1:3]) == {"b", "c"}
    assert active["max"] >= 2  # b and c overlapped


# --- failure blocks downstream ------------------------------------------------


@pytest.mark.asyncio
async def test_failed_prerequisite_blocks_dependents():
    org = _dag_org()
    org._tasks = [
        Task(description="root", id="root"),
        Task(description="child", id="child", depends_on=["root"]),
    ]

    async def fail(_messages):
        raise RuntimeError("boom")

    result = await org.arun_dag(brain=AsyncMockBrain(reply_fn=fail))
    statuses = {t.id: t.status for t in org._tasks}
    assert statuses["root"] == "failed"
    assert statuses["child"] == "failed"  # skipped, not run
    assert "prerequisite" in org._tasks[1].error
    assert result.succeeded == 0


@pytest.mark.asyncio
async def test_sibling_of_failed_task_still_runs():
    # a fails; b depends on a (blocked); c is independent (runs).
    org = _dag_org()
    ran: list[str] = []

    async def maybe_fail(messages):
        # The user prompt is the task description.
        text = messages[-1].content
        if "a-task" in text:
            raise RuntimeError("boom")
        return "ok"

    org._tasks = [
        Task(description="a-task", id="a"),
        Task(description="b-task", id="b", depends_on=["a"]),
        Task(description="c-task", id="c"),
    ]
    await org.arun_dag(
        brain=AsyncMockBrain(reply_fn=maybe_fail),
        on_task_done=lambda t: ran.append(t.id),
    )
    statuses = {t.id: t.status for t in org._tasks}
    assert statuses["a"] == "failed"
    assert statuses["b"] == "failed"  # blocked
    assert statuses["c"] == "done"    # independent, ran anyway


# --- end-to-end: plan -> enqueue -> arun_dag ----------------------------------


@pytest.mark.asyncio
async def test_dependent_task_receives_prerequisite_results():
    org = _dag_org()
    org._tasks = [
        Task(description="compute A", id="a"),
        Task(description="combine with A", id="b", depends_on=["a"]),
    ]
    captured = {}

    async def reply(messages):
        text = messages[-1].content
        if "Results from prerequisite tasks:" in text:
            captured["b_prompt"] = text      # this is task b
            return "combined"
        return "A=42"                         # task a

    await org.arun_dag(brain=AsyncMockBrain(reply_fn=reply))
    assert org._tasks[0].result == "A=42"
    # b's prompt carried a's result AND what produced it.
    assert "A=42" in captured["b_prompt"]
    assert "compute A" in captured["b_prompt"]
    assert "Your task: combine with A" in captured["b_prompt"]


@pytest.mark.asyncio
async def test_fan_in_receives_all_prerequisite_results():
    org = _dag_org()
    org._tasks = [
        Task(description="produce X", id="x"),
        Task(description="produce Y", id="y"),
        Task(description="sum X and Y", id="z", depends_on=["x", "y"]),
    ]
    captured = {}

    async def reply(messages):
        text = messages[-1].content
        if "sum X and Y" in text and "prerequisite" in text:
            captured["z"] = text
            return "10"
        return "3" if "produce X" in text else "7"

    await org.arun_dag(brain=AsyncMockBrain(reply_fn=reply), concurrency=4)
    # z saw both upstream results.
    assert "3" in captured["z"] and "7" in captured["z"]
    assert "produce X" in captured["z"] and "produce Y" in captured["z"]


@pytest.mark.asyncio
async def test_independent_task_prompt_is_unchanged():
    org = _dag_org()
    org._tasks = [Task(description="standalone", id="s")]
    captured = {}

    async def reply(messages):
        captured["p"] = messages[-1].content
        return "ok"

    await org.arun_dag(brain=AsyncMockBrain(reply_fn=reply))
    assert captured["p"] == "standalone"  # no dependency preamble


@pytest.mark.asyncio
async def test_plan_enqueue_arun_dag_end_to_end():
    org = Ormica("Acme")
    plan_reply = json.dumps(
        {"steps": [{"description": "gather"},
                   {"description": "summarize", "depends_on": [1]}]}
    )
    plan = org.plan("research the market", brain=MockBrain(replies=[plan_reply]))
    org.enqueue_plan(plan)

    order: list[str] = []
    result = await org.arun_dag(
        brain=AsyncMockBrain(reply_fn=lambda _m: "ok"),
        on_task_done=lambda t: order.append(t.description),
    )
    assert result.succeeded == 2
    assert order == ["gather", "summarize"]
