"""Tests for the task-decomposition planner."""
import json

import pytest

from ormica import (
    AsyncPlanner,
    Ormica,
    Plan,
    PlanError,
    PlannedStep,
    Planner,
    Task,
)
from ormica.brain import AsyncMockBrain, MockBrain
from ormica.planner import _extract_json, _parse_steps, _toposort


def _reply(steps) -> str:
    return json.dumps({"steps": steps})


# --- parsing ------------------------------------------------------------------


def test_parse_flat_steps_with_target_and_priority():
    steps = _parse_steps(
        _reply(
            [
                {"description": "draft copy", "target": "marketing", "priority": "high"},
                {"description": "send it", "depends_on": [1]},
            ]
        )
    )
    assert [s.description for s in steps] == ["draft copy", "send it"]
    assert steps[0].target == "marketing"
    assert steps[0].priority == "high"
    # depends_on index 1 -> first step's id
    assert steps[1].depends_on == [steps[0].id]


def test_parse_accepts_bare_list_and_string_items():
    steps = _parse_steps(json.dumps(["do a", "do b"]))
    assert [s.description for s in steps] == ["do a", "do b"]


def test_extract_json_from_prose_and_fences():
    wrapped = 'Sure! Here is the plan:\n```json\n{"steps": [{"description": "x"}]}\n```\nDone.'
    assert json.loads(_extract_json(wrapped)) == {"steps": [{"description": "x"}]}


def test_parse_rejects_non_json():
    with pytest.raises(PlanError, match="no JSON"):
        _parse_steps("I cannot help with that.")


def test_parse_rejects_invalid_depends_on():
    with pytest.raises(PlanError, match="invalid depends_on"):
        _parse_steps(_reply([{"description": "x", "depends_on": [5]}]))


# --- topological ordering -----------------------------------------------------


def test_toposort_orders_dependencies_first():
    steps = _parse_steps(
        _reply(
            [
                {"description": "publish", "depends_on": [2]},
                {"description": "write"},
            ]
        )
    )
    order = [s.description for s in _toposort(steps)]
    assert order == ["write", "publish"]


def test_toposort_detects_cycle():
    a = PlannedStep(description="a", id="a")
    b = PlannedStep(description="b", id="b")
    a.depends_on = ["b"]
    b.depends_on = ["a"]
    with pytest.raises(PlanError, match="cycle"):
        _toposort([a, b])


# --- Planner ------------------------------------------------------------------


def test_planner_flat_decomposition():
    brain = MockBrain(
        replies=[_reply([{"description": "step 1"}, {"description": "step 2"}])]
    )
    plan = Planner(brain).plan("do the thing")
    assert isinstance(plan, Plan)
    assert len(plan) == 2
    assert len(plan.leaves()) == 2


def test_planner_passes_targets_into_prompt():
    brain = MockBrain(replies=[_reply([{"description": "x"}])])
    Planner(brain).plan("goal", targets=["sales", "eng"])
    prompt_text = brain.calls[0][0].content
    assert "sales" in prompt_text and "eng" in prompt_text


def test_planner_recursive_decomposition():
    # max_depth=2 => top level expands once; substeps sit at depth 1 (leaves).
    brain = MockBrain(
        replies=[
            _reply([{"description": "A"}, {"description": "B"}]),   # top level
            _reply([{"description": "A1"}, {"description": "A2"}]),  # expand A
            _reply([{"description": "B1"}, {"description": "B2"}]),  # expand B
        ]
    )
    plan = Planner(brain).plan("big goal", max_depth=2)
    assert len(plan.steps) == 2
    assert not plan.steps[0].is_leaf  # A was decomposed
    leaves = [s.description for s in plan.leaves()]
    assert leaves == ["A1", "A2", "B1", "B2"]


def test_planner_stops_recursing_when_step_is_atomic():
    # A expands to 2 subs; B's decomposition returns 1 step => B stays a leaf.
    brain = MockBrain(
        replies=[
            _reply([{"description": "A"}, {"description": "B"}]),
            _reply([{"description": "A1"}, {"description": "A2"}]),  # expand A
            _reply([{"description": "B itself"}]),                   # B atomic -> leaf
        ]
    )
    plan = Planner(brain).plan("goal", max_depth=2)
    assert not plan.steps[0].is_leaf
    assert plan.steps[1].is_leaf
    assert [s.description for s in plan.leaves()] == ["A1", "A2", "B"]


def test_planner_rejects_bad_max_depth():
    with pytest.raises(ValueError):
        Planner(MockBrain(replies=["{}"])).plan("g", max_depth=0)


# --- to_tasks -----------------------------------------------------------------


def test_to_tasks_in_dependency_order():
    brain = MockBrain(
        replies=[
            _reply(
                [
                    {"description": "deploy", "depends_on": [2], "priority": "high"},
                    {"description": "build"},
                ]
            )
        ]
    )
    plan = Planner(brain).plan("ship")
    tasks = plan.to_tasks()
    assert all(isinstance(t, Task) for t in tasks)
    assert [t.description for t in tasks] == ["build", "deploy"]
    assert tasks[1].priority == "high"


def test_pretty_renders_tree():
    plan = Planner(
        MockBrain(replies=[_reply([{"description": "root step", "target": "eng"}])])
    ).plan("goal")
    text = plan.pretty()
    assert "Goal: goal" in text
    assert "root step" in text and "@eng" in text


# --- facade integration -------------------------------------------------------


def test_org_plan_enqueue_and_run():
    org = Ormica("Acme")
    org.plant("business")
    plan_brain = MockBrain(
        replies=[_reply([{"description": "research leads"}, {"description": "email leads"}])]
    )
    plan = org.plan("grow revenue", brain=plan_brain)
    added = org.enqueue_plan(plan)
    assert len(added) == 2
    assert len(org.pending_tasks()) == 2

    exec_brain = MockBrain(replies=["done"])
    result = org.run(brain=exec_brain)
    assert result.succeeded == 2


# --- async parity -------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_planner():
    brain = AsyncMockBrain(
        replies=[_reply([{"description": "a"}, {"description": "b"}])]
    )
    plan = await AsyncPlanner(brain).plan("goal")
    assert [s.description for s in plan.steps] == ["a", "b"]
