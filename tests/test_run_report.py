"""Tests for the run report — tokens and duration surfaced on RunResult."""
from ormica import Ormica
from ormica.brain import MockBrain


def test_runresult_reports_tokens_and_time():
    org = Ormica("Acme")
    org.spawn("w", role="w")
    org.task("do a thing", target="w")
    org.task("do another thing", target="w")

    result = org.run(brain=MockBrain(reply_fn=lambda m: "a fairly long answer here"))

    assert result.processed == 2 and result.succeeded == 2
    assert result.tokens_used > 0                    # summed across tasks
    assert result.tokens_used == sum(t.tokens_used for t in org.tasks)
    assert result.seconds >= 0.0
    assert "tokens=" in result.summary() and "in " in result.summary()


def test_each_task_records_its_tokens():
    org = Ormica("Acme")
    org.spawn("w")
    org.task("x", target="w")
    org.run(brain=MockBrain(replies=["some answer"]))
    assert org.tasks[0].tokens_used > 0
