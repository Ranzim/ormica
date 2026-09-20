"""Tests for the grounding framework — verify against real oracles."""
import os

import pytest

from ormica import Agent
from ormica.arbor import Tree
from ormica.brain import MockBrain
from ormica.cortex import (
    CheckResult,
    Constitution,
    Rule,
    VerificationFailed,
    grounded,
    judge_oracle,
    sandbox_oracle,
)

posix = pytest.mark.skipif(os.name != "posix", reason="sandbox oracle needs POSIX")


# --- CheckResult flows into the verify feedback -------------------------------


def test_check_result_reason_becomes_violation_reason():
    rule = Rule(
        name="r", description="d", stage="verify",
        check=lambda ctx: CheckResult(False, "printed 41, expected 42", score=0.0),
    )
    v = rule.evaluate({"response": None})
    assert v is not None
    assert v.reason == "printed 41, expected 42"
    assert v.context["score"] == 0.0


def test_check_result_ok_passes():
    rule = Rule(name="r", description="d", check=lambda ctx: CheckResult(True))
    assert rule.evaluate({}) is None


def test_bool_check_still_works():
    assert Rule(name="r", description="d", check=lambda ctx: True).evaluate({}) is None
    assert Rule(name="r", description="d", check=lambda ctx: False).evaluate({}) is not None


# --- sandbox oracle -----------------------------------------------------------


@posix
def test_sandbox_oracle_expected_match():
    oracle = sandbox_oracle(expected="42")
    from types import SimpleNamespace
    ctx = {"response": SimpleNamespace(content="print(6 * 7)")}
    assert grounded(oracle).check(ctx).ok is True
    bad = {"response": SimpleNamespace(content="print(6 * 8)")}
    res = grounded(oracle).check(bad)
    assert res.ok is False and "expected '42'" in res.reason


@posix
def test_sandbox_oracle_reports_errors():
    oracle = sandbox_oracle(expected="1")
    res = oracle("raise ValueError('boom')", {})
    assert res.ok is False and "errored" in res.reason


@posix
def test_sandbox_oracle_checker_and_fences():
    # checker predicate + markdown-fenced code extraction
    oracle = sandbox_oracle(checker=lambda out: int(out) > 100)
    res = oracle("```python\nprint(500)\n```", {})
    assert res.ok is True


# --- judge oracle -------------------------------------------------------------


def test_judge_oracle_pass_and_fail():
    good = judge_oracle(MockBrain(replies=["PASS"]), "must be polite")
    assert good("hello!", {}).ok is True
    bad = judge_oracle(MockBrain(replies=["FAIL: rude tone"]), "must be polite")
    r = bad("go away", {})
    assert r.ok is False and r.reason == "rude tone"


# --- end-to-end: grounding drives verify retry --------------------------------


@posix
def test_grounding_drives_verify_retry():
    # first answer prints the wrong number, second is corrected.
    con = Constitution([grounded(sandbox_oracle(expected="42"))])
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "analyst")
    brain = MockBrain(replies=["print(41)", "print(42)"])
    agent = Agent(node, brain, constitution=con)
    resp = agent.act("compute 6*7 in python that prints the number")
    assert resp.content == "print(42)"
    # the retry prompt carried the oracle's reason
    assert any("expected '42'" in m.content for m in brain.calls[-1])


@posix
def test_grounding_gives_up_when_never_correct():
    con = Constitution([grounded(sandbox_oracle(expected="42"))])
    tree = Tree("HQ")
    node = tree.spawn(tree.root, "analyst")
    agent = Agent(node, MockBrain(reply_fn=lambda m: "print(0)"), constitution=con)
    with pytest.raises(VerificationFailed):
        agent.act("compute", max_verify_attempts=2)
