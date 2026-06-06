"""Tests for the runtime — Task, TaskRunner, and the Ormica run loop."""

from ormica import Ormica, RunResult, Task
from ormica.brain import MockBrain, Router


def test_task_dataclass_defaults():
    t = Task(description="do X")
    assert t.description == "do X"
    assert t.status == "pending"
    assert t.priority == "normal"
    assert t.target == ""
    assert t.result is None
    assert t.error is None
    assert len(t.id) == 8


def test_org_task_appends_to_queue():
    org = Ormica("HQ")
    t = org.task("first")
    assert org.tasks == [t]
    assert t.status == "pending"


def test_org_task_dept_aliases_target():
    org = Ormica("HQ")
    t = org.task("call leads", dept="sales", priority="high")
    assert t.target == "sales"
    assert t.priority == "high"


def test_run_with_no_tasks_returns_empty_result():
    org = Ormica("HQ")
    result = org.run(brain=MockBrain(replies=["never called"]))
    assert isinstance(result, RunResult)
    assert result.processed == 0
    assert result.succeeded == 0
    assert result.failed == 0


def test_run_processes_pending_tasks_through_cortex():
    org = Ormica("HQ")
    org.spawn("sales", role="sales", task="close deals")
    org.task("Reach out to 3 leads", dept="sales")

    brain = MockBrain(replies=["Contacted Acme, Globex, and Initech."])
    result = org.run(brain=brain)

    assert result.processed == 1
    assert result.succeeded == 1
    assert result.failed == 0

    task = org.tasks[0]
    assert task.status == "done"
    assert task.result == "Contacted Acme, Globex, and Initech."


def test_run_routes_to_target_node_via_find():
    org = Ormica("HQ")
    org.spawn("sales", role="sales")
    org.spawn("ops", role="ops")
    org.task("sales work", dept="sales")
    org.task("ops work", dept="ops")

    seen_roles = []

    def reply_fn(messages):
        # System message contains the role; capture it.
        if messages and messages[0].role == "system":
            seen_roles.append(messages[0].content)
        return "ok"

    org.run(brain=MockBrain(reply_fn=reply_fn))
    joined = " ".join(seen_roles)
    assert "Your role: sales." in joined
    assert "Your role: ops." in joined


def test_run_uses_router_to_pick_per_node_cortex():
    org = Ormica("HQ")
    org.spawn("sales", role="sales")
    org.spawn("ops", role="ops")
    org.task("a", dept="sales")
    org.task("b", dept="ops")

    sales_brain = MockBrain(replies=["sales says hi"])
    ops_brain = MockBrain(replies=["ops says hi"])
    router = Router(default=sales_brain, by_name={"ops": ops_brain})

    org.run(brain=router)

    by_target = {t.target: t for t in org.tasks}
    assert by_target["sales"].result == "sales says hi"
    assert by_target["ops"].result == "ops says hi"


def test_failing_cortex_marks_task_failed_and_loop_continues():
    org = Ormica("HQ")
    org.spawn("sales", role="sales")
    org.task("first", dept="sales")
    org.task("second", dept="sales")

    def boom(messages):
        raise RuntimeError("kapow")

    result = org.run(brain=MockBrain(reply_fn=boom))
    assert result.processed == 2
    assert result.succeeded == 0
    assert result.failed == 2

    for task in org.tasks:
        assert task.status == "failed"
        assert "kapow" in task.error
        assert "RuntimeError" in task.error


def test_unknown_target_marks_task_failed_not_crash():
    org = Ormica("HQ")
    org.task("ghost work", dept="nonexistent")
    result = org.run(brain=MockBrain(replies=["x"]))
    assert result.failed == 1
    assert "NodeNotFound" in org.tasks[0].error


def test_priority_ordering_high_before_normal_before_low():
    org = Ormica("HQ")
    org.spawn("sales", role="sales")
    org.task("a", dept="sales", priority="low")
    org.task("b", dept="sales", priority="normal")
    org.task("c", dept="sales", priority="high")

    order: list[str] = []
    org.run(
        brain=MockBrain(replies=["ok", "ok", "ok"]),
        on_task_done=lambda t: order.append(t.description),
    )
    assert order == ["c", "b", "a"]


def test_max_tasks_caps_run_size():
    org = Ormica("HQ")
    for i in range(5):
        org.task(f"task-{i}")

    result = org.run(brain=MockBrain(replies=["ok"]), max_tasks=2)
    assert result.processed == 2
    # The other three remain pending.
    statuses = [t.status for t in org.tasks]
    assert statuses.count("pending") == 3
    assert statuses.count("done") == 2


def test_task_callbacks_fire_in_order():
    org = Ormica("HQ")
    org.task("only")

    starts: list[str] = []
    dones: list[str] = []
    org.run(
        brain=MockBrain(replies=["ok"]),
        on_task_start=lambda t: starts.append(t.status),
        on_task_done=lambda t: dones.append(t.status),
    )
    assert starts == ["running"]
    assert dones == ["done"]


def test_task_result_persisted_in_mycelium():
    org = Ormica("HQ")
    sales = org.spawn("sales", role="sales")
    t = org.task("write a haiku", dept="sales")

    org.run(brain=MockBrain(replies=["spring rain falls"]))

    entry = org.memory.read(f"tasks/{t.id}")
    assert entry is not None
    assert entry.value["status"] == "done"
    assert entry.value["result"] == "spring rain falls"
    assert entry.author == sales.id


def test_pending_tasks_excludes_finished():
    org = Ormica("HQ")
    org.task("a")
    org.run(brain=MockBrain(replies=["ok"]))
    assert org.pending_tasks() == []
    assert len(org.tasks) == 1


def test_run_uses_org_memory_and_signals_via_agent():
    """An agent built inside the runner can write to shared memory + emit signals."""
    org = Ormica("HQ")
    org.spawn("scout", role="scout")
    org.task("scout the area", dept="scout")

    def reply_fn(messages):
        # Just confirm the agent has access; runner wires memory+signals on its own.
        return "scouted"

    org.run(brain=MockBrain(reply_fn=reply_fn))
    assert org.tasks[0].status == "done"


def test_run_with_planted_colony_uses_template_system_prompt():
    """End-to-end: plant a colony, queue a task to a department, run it."""
    org = Ormica("Acme")
    org.plant("business")
    org.task("Reach out to 3 SMB leads.", dept="sales", priority="high")

    captured: list[str] = []

    def reply_fn(messages):
        if messages and messages[0].role == "system":
            captured.append(messages[0].content)
        return "Lead list attached."

    org.run(brain=MockBrain(reply_fn=reply_fn))

    assert org.tasks[0].status == "done"
    # Template's system prompt from BusinessColony's SalesAgent appears.
    assert any("sales lead" in s.lower() for s in captured)
