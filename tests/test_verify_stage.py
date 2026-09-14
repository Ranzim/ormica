"""Tests for the cortex verify stage — check-and-retry on responses."""
import pytest

from ormica import Agent, AsyncAgent
from ormica.arbor import Tree
from ormica.brain import AsyncMockBrain, MockBrain
from ormica.cortex import (
    Constitution,
    Rule,
    VerificationFailed,
    must_be_json,
    must_contain,
    must_match,
    verifier,
)
from ormica.observe import VERIFY_FAILED, VERIFY_RETRY, CollectObserver, EventBus


def _agent(brain, rules, *, events=None) -> Agent:
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    agent = Agent(node, brain, constitution=Constitution(rules))
    if events is not None:
        agent.events = events
    return agent


# --- factories are verify-stage rules -----------------------------------------


def test_factories_produce_verify_stage_rules():
    for rule in (must_be_json(), must_contain("x"), must_match(r"\d+")):
        assert isinstance(rule, Rule)
        assert rule.stage == "verify"
        assert rule.severity == "hard"


# --- pass / retry / give up ---------------------------------------------------


def test_passes_first_time_no_retry():
    brain = MockBrain(replies=['{"ok": true}'])
    agent = _agent(brain, [must_be_json()])
    resp = agent.act("give me json")
    assert resp.content == '{"ok": true}'
    assert len(brain.calls) == 1  # no retry


def test_retries_then_passes_and_feeds_back_the_reason():
    # First answer is not JSON; second is.
    brain = MockBrain(replies=["not json at all", '{"ok": 1}'])
    agent = _agent(brain, [must_be_json()])
    resp = agent.act("emit json")
    assert resp.content == '{"ok": 1}'
    assert len(brain.calls) == 2
    # The retry prompt must carry the failed answer + a correction note.
    retry_msgs = brain.calls[1]
    roles = [m.role for m in retry_msgs]
    assert "assistant" in roles  # previous answer echoed back
    assert any("failed verification" in m.content for m in retry_msgs)
    assert any("must be valid JSON" in m.content for m in retry_msgs)


def test_gives_up_after_max_attempts():
    brain = MockBrain(reply_fn=lambda _m: "never json")
    agent = _agent(brain, [must_be_json()])
    with pytest.raises(VerificationFailed) as exc:
        agent.act("json please", max_verify_attempts=3)
    assert exc.value.attempts == 3
    assert len(brain.calls) == 3
    assert agent.node.state.name == "FAILED"


def test_max_verify_attempts_one_means_no_retry():
    brain = MockBrain(replies=["bad", "good json {}"])
    agent = _agent(brain, [must_be_json()])
    with pytest.raises(VerificationFailed):
        agent.act("json", max_verify_attempts=1)
    assert len(brain.calls) == 1


def test_invalid_max_verify_attempts():
    agent = _agent(MockBrain(replies=["x"]), [must_be_json()])
    with pytest.raises(ValueError):
        agent.act("x", max_verify_attempts=0)


# --- severity + no-op ---------------------------------------------------------


def test_soft_verify_rule_does_not_retry_or_raise():
    soft = verifier("soft_json", lambda ctx: False, severity="soft")
    brain = MockBrain(replies=["anything"])
    agent = _agent(brain, [soft])
    resp = agent.act("go")
    assert resp.content == "anything"
    assert len(brain.calls) == 1  # soft failure: proceed, no retry


def test_no_verify_rules_is_unchanged_single_call():
    brain = MockBrain(replies=["hello"])
    agent = _agent(brain, [])
    resp = agent.act("hi")
    assert resp.content == "hello"
    assert len(brain.calls) == 1
    assert agent.node.state.name == "DONE"


def test_custom_verifier_sees_attempt_number():
    seen: list[int] = []

    def check(ctx) -> bool:
        seen.append(ctx["attempt"])
        return ctx["attempt"] >= 2  # fail first attempt, pass second

    brain = MockBrain(replies=["a", "b"])
    agent = _agent(brain, [verifier("attempt_aware", check)])
    agent.act("go")
    assert seen == [1, 2]


# --- other factories ----------------------------------------------------------


def test_must_contain_and_must_match():
    brain = MockBrain(replies=["the answer is 42"])
    agent = _agent(brain, [must_contain("answer"), must_match(r"\d+")])
    assert agent.act("q").content == "the answer is 42"


# --- events -------------------------------------------------------------------


def test_emits_retry_and_failed_events():
    bus = EventBus()
    collector = CollectObserver()
    bus.subscribe(collector)
    brain = MockBrain(reply_fn=lambda _m: "nope")
    agent = _agent(brain, [must_be_json()], events=bus)
    with pytest.raises(VerificationFailed):
        agent.act("json", max_verify_attempts=2)
    types = [e.type for e in collector.events]
    assert types.count(VERIFY_RETRY) == 1  # one retry between 2 attempts
    assert VERIFY_FAILED in types


# --- async parity -------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_retries_then_passes():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    brain = AsyncMockBrain(replies=["not json", "{}"])
    agent = AsyncAgent(node, brain, constitution=Constitution([must_be_json()]))
    resp = await agent.act("json")
    assert resp.content == "{}"
    assert len(brain.calls) == 2


@pytest.mark.asyncio
async def test_async_gives_up():
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "worker")
    brain = AsyncMockBrain(reply_fn=lambda _m: "bad")
    agent = AsyncAgent(node, brain, constitution=Constitution([must_be_json()]))
    with pytest.raises(VerificationFailed):
        await agent.act("json", max_verify_attempts=2)
