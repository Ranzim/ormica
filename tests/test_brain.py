"""Tests for brain — protocol, mock, token budget, router."""
import pytest

from ormica.arbor import Node
from ormica.brain import (
    BudgetExhausted,
    Brain,
    Message,
    MockBrain,
    Response,
    Router,
    TokenBudget,
    to_messages,
)


def test_to_messages_normalises_string_to_user_turn():
    msgs = to_messages("hello")
    assert msgs == [Message(role="user", content="hello")]


def test_to_messages_preserves_existing_list():
    given = [Message(role="user", content="a"), Message(role="assistant", content="b")]
    assert to_messages(given) == given


def test_mock_cortex_requires_exactly_one_reply_source():
    with pytest.raises(ValueError):
        MockBrain()
    with pytest.raises(ValueError):
        MockBrain(replies=["x"], reply_fn=lambda _: "y")


def test_mock_cortex_cycles_replies_and_records_calls():
    brain = MockBrain(replies=["one", "two"])

    r1 = brain.think("first")
    r2 = brain.think("second")
    r3 = brain.think("third")

    assert (r1.content, r2.content, r3.content) == ("one", "two", "one")
    assert len(brain.calls) == 3
    assert brain.calls[0] == [Message(role="user", content="first")]


def test_mock_cortex_reply_fn_receives_normalised_messages():
    seen = []

    def fn(messages: list[Message]) -> str:
        seen.append(messages)
        return f"got {len(messages)} messages"

    brain = MockBrain(reply_fn=fn)
    brain.think("hi", system="you are terse")

    assert seen[0][0].role == "system"
    assert seen[0][1].role == "user"


def test_mock_cortex_satisfies_cortex_protocol():
    assert isinstance(MockBrain(replies=["x"]), Brain)


def test_mock_cortex_response_has_model_and_tokens():
    brain = MockBrain(replies=["a sentence with words"])
    resp = brain.think("anything")
    assert resp.model == "mock"
    assert resp.tokens_used > 0
    assert resp.finish_reason == "stop"


# --- TokenBudget ---


def test_token_budget_tracks_usage():
    budget = TokenBudget(limit=100)
    assert budget.remaining == 100
    assert not budget.exhausted

    budget.consume(40)
    assert budget.used == 40
    assert budget.remaining == 60
    assert budget.can_afford(60)
    assert not budget.can_afford(61)


def test_token_budget_exhausted_at_limit():
    budget = TokenBudget(limit=10)
    budget.consume(10)
    assert budget.exhausted
    assert budget.remaining == 0


def test_token_budget_rejects_negative_consumption():
    with pytest.raises(ValueError):
        TokenBudget(limit=10).consume(-1)


# --- Router ---


def test_router_falls_back_to_default():
    default = MockBrain(replies=["d"])
    router = Router(default=default)
    node = Node(name="random", role="unknown")

    assert router.for_node(node) is default


def test_router_resolves_by_name_first():
    default = MockBrain(replies=["d"])
    scout = MockBrain(replies=["s"])
    exec_ = MockBrain(replies=["e"])
    router = Router(
        default=default,
        by_role={"executive": exec_},
        by_name={"scout-7": scout},
    )

    assert router.for_node(Node(name="scout-7", role="executive")) is scout
    assert router.for_node(Node(name="ceo", role="executive")) is exec_
    assert router.for_node(Node(name="other", role="other")) is default
