"""Async self-healing (arun heal=) + the max_tasks silent-cap warning."""
import pytest

from ormica import HealingPolicy, Ormica
from ormica.brain import AsyncMockBrain, MockBrain


def _boom(_messages):
    raise RuntimeError("always fails")


@pytest.mark.asyncio
async def test_async_task_retries_then_succeeds():
    calls = {}

    def flaky(messages):
        key = messages[-1].content
        calls[key] = calls.get(key, 0) + 1
        if calls[key] == 1:
            raise RuntimeError("transient")
        return "recovered"

    org = Ormica("A")
    org.spawn("w", role="w")
    org.task("do it", target="w")
    await org.arun(brain=AsyncMockBrain(reply_fn=flaky), heal=HealingPolicy(max_retries=2))

    assert org.tasks[0].status == "done" and org.tasks[0].result == "recovered"
    assert calls["do it"] == 2


@pytest.mark.asyncio
async def test_async_exhausted_is_dead_lettered():
    org = Ormica("A")
    org.spawn("w")
    org.task("x", target="w")
    seen = []
    org.subscribe(type("O", (), {"notify": lambda self, e: seen.append(e.type)})())

    await org.arun(brain=AsyncMockBrain(reply_fn=_boom),
                   heal=HealingPolicy(max_retries=1, circuit_threshold=99))

    t = org.tasks[0]
    assert t.status == "dead"
    assert t in org.dead_letter
    assert "task.dead" in seen


@pytest.mark.asyncio
async def test_async_no_heal_leaves_failure_as_is():
    org = Ormica("A")
    org.spawn("w")
    org.task("x", target="w")
    await org.arun(brain=AsyncMockBrain(reply_fn=_boom))     # no heal
    assert org.tasks[0].status == "failed"                   # not retried, not dead


# --- the max_tasks silent-cap warning ----------------------------------------


def test_run_warns_when_tasks_exceed_max_tasks():
    org = Ormica("A")
    for i in range(5):
        org.task(f"t{i}")
    with pytest.warns(UserWarning, match="max_tasks=2"):
        org.run(brain=MockBrain(reply_fn=lambda m: "ok"), max_tasks=2)
    assert sum(1 for t in org.tasks if t.status == "done") == 2   # only the cap ran


def test_run_does_not_warn_within_cap():
    import warnings

    org = Ormica("A")
    org.task("only one")
    with warnings.catch_warnings():
        warnings.simplefilter("error")           # any warning would fail the test
        org.run(brain=MockBrain(reply_fn=lambda m: "ok"))
