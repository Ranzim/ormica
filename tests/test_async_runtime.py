"""Tests for AsyncAgent, AsyncTaskRunner, and Ormica.arun()."""
import asyncio

import pytest

from ormica import AsyncAgent, Ormica
from ormica.arbor import NodeState, Tree
from ormica.brain import AsyncMockBrain, BudgetExhausted, Router, TokenBudget
from ormica.mycelium import Mycelium
from ormica.stigma import Stigma


# --- AsyncAgent --------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_agent_acts_and_marks_done():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "scout")
    agent = AsyncAgent(node, AsyncMockBrain(replies=["ok"]))

    resp = await agent.act("go")
    assert resp.content == "ok"
    assert node.state == NodeState.DONE


@pytest.mark.asyncio
async def test_async_agent_failed_marks_node_failed():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "scout")

    async def boom(_messages):
        raise RuntimeError("kapow")

    agent = AsyncAgent(node, AsyncMockBrain(reply_fn=boom))
    with pytest.raises(RuntimeError, match="kapow"):
        await agent.act("go")
    assert node.state == NodeState.FAILED


@pytest.mark.asyncio
async def test_async_agent_budget_exhausted_blocks_call():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "scout")
    brain = AsyncMockBrain(replies=["should not be called"])
    agent = AsyncAgent(node, brain, budget=TokenBudget(limit=10, used=10))

    with pytest.raises(BudgetExhausted):
        await agent.act("hi")
    assert brain.calls == []


@pytest.mark.asyncio
async def test_async_agent_composes_system_with_role_and_task():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "scout", role="recon", task="map area")
    brain = AsyncMockBrain(replies=["ok"])
    agent = AsyncAgent(node, brain, system_prompt="Be quiet.")

    await agent.act("go")
    system_msg = brain.calls[0][0]
    assert system_msg.role == "system"
    text = system_msg.content
    assert "Be quiet." in text
    assert "Your role: recon." in text
    assert "Your task: map area" in text


@pytest.mark.asyncio
async def test_async_agent_emit_and_recall_use_org_layers():
    mem = Mycelium()
    stig = Stigma(mem)
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "scout")
    agent = AsyncAgent(node, AsyncMockBrain(replies=["x"]), memory=mem, signals=stig)

    agent.remember("found", "acme")
    agent.emit("hot_lead", strength=2.0)
    assert agent.recall("found") == "acme"
    assert agent.sense("hot_lead").strength == pytest.approx(2.0)


# --- AsyncTaskRunner / Ormica.arun() -----------------------------------------


@pytest.mark.asyncio
async def test_arun_processes_pending_tasks():
    org = Ormica("HQ")
    org.spawn("sales", role="sales")
    org.task("call leads", dept="sales")

    result = await org.arun(brain=AsyncMockBrain(replies=["deals booked"]))
    assert result.processed == 1
    assert result.succeeded == 1
    assert org.tasks[0].result == "deals booked"


@pytest.mark.asyncio
async def test_arun_runs_same_priority_band_concurrently():
    """A slow async brain with 3 tasks should take ~1 sleep, not 3."""
    org = Ormica("HQ")
    for i in range(3):
        org.task(f"task-{i}")

    in_flight = 0
    peak = 0

    async def slow(_messages):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return "ok"

    result = await org.arun(
        brain=AsyncMockBrain(reply_fn=slow),
        concurrency=5,
    )
    assert result.succeeded == 3
    assert peak >= 2  # at least two ran in parallel


@pytest.mark.asyncio
async def test_arun_concurrency_limit_is_respected():
    org = Ormica("HQ")
    for i in range(6):
        org.task(f"task-{i}")

    in_flight = 0
    peak = 0

    async def slow(_messages):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.03)
        in_flight -= 1
        return "ok"

    await org.arun(brain=AsyncMockBrain(reply_fn=slow), concurrency=2)
    assert peak == 2


@pytest.mark.asyncio
async def test_arun_priority_bands_run_sequentially():
    """All high-priority tasks finish before any normal-priority task starts."""
    org = Ormica("HQ")
    org.task("low-a",  priority="low")
    org.task("high-a", priority="high")
    org.task("normal-a")
    org.task("high-b", priority="high")
    org.task("normal-b")

    start_order: list[str] = []

    async def record(messages):
        # The user content of a task is its description.
        user_msg = next(m for m in messages if m.role == "user")
        start_order.append(user_msg.content)
        await asyncio.sleep(0)
        return "ok"

    await org.arun(brain=AsyncMockBrain(reply_fn=record), concurrency=10)

    high_idx = [i for i, name in enumerate(start_order) if name.startswith("high")]
    normal_idx = [i for i, name in enumerate(start_order) if name.startswith("normal")]
    low_idx = [i for i, name in enumerate(start_order) if name.startswith("low")]
    # Highest index of one band < lowest index of next.
    assert max(high_idx) < min(normal_idx)
    assert max(normal_idx) < min(low_idx)


@pytest.mark.asyncio
async def test_arun_failure_does_not_abort_run():
    org = Ormica("HQ")
    org.task("ok-task")
    org.task("bad-task")

    async def reply_fn(messages):
        user_text = next(m.content for m in messages if m.role == "user")
        if "bad" in user_text:
            raise RuntimeError("boom")
        return "fine"

    result = await org.arun(brain=AsyncMockBrain(reply_fn=reply_fn))
    assert result.processed == 2
    assert result.succeeded == 1
    assert result.failed == 1


@pytest.mark.asyncio
async def test_arun_uses_router_to_pick_per_node_cortex():
    org = Ormica("HQ")
    org.spawn("sales", role="sales")
    org.spawn("ops", role="ops")
    org.task("a", dept="sales")
    org.task("b", dept="ops")

    sales = AsyncMockBrain(replies=["sales says hi"])
    ops = AsyncMockBrain(replies=["ops says hi"])
    router = Router(default=sales, by_name={"ops": ops})

    await org.arun(brain=router)

    by_target = {t.target: t for t in org.tasks}
    assert by_target["sales"].result == "sales says hi"
    assert by_target["ops"].result == "ops says hi"


@pytest.mark.asyncio
async def test_arun_unknown_target_marks_task_failed():
    org = Ormica("HQ")
    org.task("ghost", dept="nonexistent")
    result = await org.arun(brain=AsyncMockBrain(replies=["never used"]))
    assert result.failed == 1
    assert "NodeNotFound" in org.tasks[0].error


@pytest.mark.asyncio
async def test_arun_persists_task_results_in_mycelium():
    org = Ormica("HQ")
    scout = org.spawn("scout", role="scout")
    t = org.task("look", dept="scout")
    await org.arun(brain=AsyncMockBrain(replies=["nothing yet"]))

    entry = org.memory.read(f"tasks/{t.id}")
    assert entry is not None
    assert entry.author == scout.id
    assert entry.value["status"] == "done"
    assert entry.value["result"] == "nothing yet"


@pytest.mark.asyncio
async def test_arun_with_no_tasks_returns_empty_result():
    org = Ormica("HQ")
    result = await org.arun(brain=AsyncMockBrain(replies=["unused"]))
    assert result.processed == 0


@pytest.mark.asyncio
async def test_arun_rejects_invalid_concurrency():
    org = Ormica("HQ")
    org.task("x")
    with pytest.raises(ValueError):
        await org.arun(brain=AsyncMockBrain(replies=["x"]), concurrency=0)


@pytest.mark.asyncio
async def test_arun_with_planted_colony_picks_up_system_prompt():
    """Async path mirrors sync: planted nodes' template prompts surface."""
    org = Ormica("Acme")
    org.plant("business")
    org.task("Reach out to 3 SMB leads", dept="sales", priority="high")

    captured: list[str] = []

    async def reply_fn(messages):
        if messages and messages[0].role == "system":
            captured.append(messages[0].content)
        return "Lead list attached."

    await org.arun(brain=AsyncMockBrain(reply_fn=reply_fn))
    assert any("sales lead" in s.lower() for s in captured)
    assert org.tasks[0].status == "done"


@pytest.mark.asyncio
async def test_arun_callbacks_fire():
    org = Ormica("HQ")
    org.task("one")
    org.task("two")

    starts: list[str] = []
    dones: list[str] = []

    await org.arun(
        brain=AsyncMockBrain(replies=["ok"]),
        on_task_start=lambda t: starts.append(t.status),
        on_task_done=lambda t: dones.append(t.status),
    )
    assert starts == ["running", "running"]
    assert sorted(dones) == ["done", "done"]
