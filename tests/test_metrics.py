"""Tests for ops metrics — org.metrics() and MetricsObserver."""
from ormica import Ormica
from ormica.brain import CachingBrain, MockBrain


def test_metrics_track_a_run():
    org = Ormica("M")
    org.spawn("w", role="w")
    org.task("do a thing", target="w")
    org.task("do another", target="w")
    org.run(brain=MockBrain(reply_fn=lambda m: "a decent length answer"))

    m = org.metrics()
    assert m["tasks_done"] == 2
    assert m["failure_rate"] == 0.0
    assert m["tokens"] > 0
    assert m["spawns"] >= 1                 # spawning 'w' emitted node.spawned
    assert m["colony"]["done"] == 2         # nested health snapshot
    assert "task.done" in m["events"]


def test_metrics_report_failures_and_verify_retries():
    from ormica.cortex import verifier

    org = Ormica("M")
    node = org.spawn("w")
    node.rules = [verifier("nope", lambda ctx: False, description="always fails")]
    org.task("x", target="w")
    org.run(brain=MockBrain(reply_fn=lambda m: "y"))   # verify fails → task failed

    m = org.metrics()
    assert m["tasks_failed"] == 1
    assert m["failure_rate"] == 1.0
    assert m["verify_retries"] >= 1


def test_metrics_include_cache_hit_rate_when_given_a_caching_brain():
    org = Ormica("M")
    org.spawn("w", role="w")
    for i in range(4):
        org.task("same question", target="w")   # identical prompt → cache hits
    brain = CachingBrain(MockBrain(reply_fn=lambda m: "ok"))
    org.run(brain=brain, max_tasks=4)

    m = org.metrics(brain=brain)
    assert "cache" in m
    assert m["cache"]["cache_hits"] == 3 and m["cache"]["cache_misses"] == 1
    assert m["cache"]["cache_hit_rate"] == 0.75
