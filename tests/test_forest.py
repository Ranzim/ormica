"""Tests for the Forest — many independent colonies voting on one goal."""
import pytest

from ormica import (
    ArtifactType,
    Forest,
    ForestResult,
    Ormica,
    majority_vote,
    unanimous,
)
from ormica.brain import MockBrain


# --- majority_vote (pure reconciliation) --------------------------------------


def test_plurality_winner_and_agreement():
    r = majority_vote(["42", "42", "41", "42", "7"])
    assert r.answer == "42"
    assert r.agreement == pytest.approx(3 / 5)
    assert r.consensus is True
    assert [(v.answer, v.count) for v in r.votes] == [("42", 3), ("41", 1), ("7", 1)]
    assert r.votes[0].voters == [0, 1, 3]


def test_threshold_gates_consensus():
    # 2/5 plurality is below the default 0.5 threshold → answer, but no consensus
    r = majority_vote(["a", "a", "b", "c", "d"])
    assert r.answer == "a" and r.agreement == pytest.approx(2 / 5)
    assert r.consensus is False


def test_tie_is_not_consensus():
    r = majority_vote(["a", "a", "b", "b"])
    assert r.consensus is False           # 2–2 tie, no clear winner
    assert r.answer in {"a", "b"}         # still surfaces a plurality pick


def test_unanimous_requires_all_agree():
    assert unanimous(["x", "x", "x"]).consensus is True
    assert unanimous(["x", "x", "y"]).consensus is False


def test_custom_key_groups_by_meaning():
    # different text, same extracted value
    answers = ["the answer is 42", "42!", "forty-two"]
    import re

    def num(a):
        m = re.search(r"\d+", a)
        return m.group(0) if m else a

    r = majority_vote(answers, key=num)
    assert r.votes[0].answer in {"the answer is 42", "42!"}
    assert r.votes[0].count == 2  # both "42" texts grouped


def test_votes_on_unhashable_dicts():
    r = majority_vote([{"n": 1}, {"n": 1}, {"n": 2}])
    assert r.answer == {"n": 1}
    assert r.consensus is True


def test_empty_answers():
    r = majority_vote([])
    assert r.answer is None and r.agreement == 0.0 and r.consensus is False


# --- Forest orchestration -----------------------------------------------------


def test_forest_builds_fresh_independent_colony_per_tree():
    built = []

    def build():
        org = Ormica(f"tree-{len(built)}")
        built.append(org)
        return org

    forest = Forest(build, size=4)
    forest.solve("go", brain=MockBrain(reply_fn=lambda m: "ok"))
    assert len(built) == 4
    # distinct colonies, distinct memories (genuine independence)
    assert len({id(o) for o in built}) == 4
    assert len({id(o.memory) for o in built}) == 4


def test_forest_solve_reconciles_scripted_disagreement():
    # a pluggable attempt returns a scripted answer per tree, so we control votes
    scripted = iter(["42", "42", "41", "42", "42"])

    def attempt(org, goal, brain):
        return next(scripted)

    forest = Forest(lambda: Ormica("t"), size=5, attempt=attempt)
    result = forest.solve("compute", brain=MockBrain(replies=["x"]))
    assert isinstance(result, ForestResult)
    assert result.answer == "42"
    assert result.agreement == pytest.approx(4 / 5)
    assert result.consensus is True


def test_forest_default_attempt_uses_root_agent():
    forest = Forest(lambda: Ormica("t"), size=3)
    result = forest.solve("hi", brain=MockBrain(reply_fn=lambda m: "hello"))
    assert result.answer == "hello" and result.consensus is True
    assert result.agreement == 1.0


def test_forest_rejects_zero_size():
    with pytest.raises(ValueError, match="at least one tree"):
        Forest(lambda: Ormica("t"), size=0)


def test_forest_with_typed_artifact_key():
    # trees emit JSON; vote on the parsed artifact data, not the raw text
    Est = ArtifactType("e", {"n": int})
    texts = ['{"n": 42}', '{"n": 42}', '{"n": 7}']
    scripted = iter(texts)
    forest = Forest(
        lambda: Ormica("t"),
        size=3,
        attempt=lambda org, goal, brain: Est.parse(next(scripted)),
        reconcile=lambda answers: majority_vote(answers, key=lambda a: a.data),
    )
    result = forest.solve("estimate", brain=MockBrain(replies=["x"]))
    assert result.answer.get("n") == 42
    assert result.consensus is True


@pytest.mark.asyncio
async def test_forest_asolve_runs_concurrently():
    forest = Forest(lambda: Ormica("t"), size=6)
    result = await forest.asolve(
        "q", brain=MockBrain(reply_fn=lambda m: "yes"), concurrency=3
    )
    assert result.answer == "yes"
    assert len(result.answers) == 6
    assert result.consensus is True
