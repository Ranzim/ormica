"""Tests for CachingBrain — memoize identical LLM calls."""
from ormica.brain import CachingBrain, MockBrain
from ormica.brain.tool import ToolCall


def test_identical_prompt_hits_cache_once():
    calls = []
    inner = MockBrain(reply_fn=lambda m: (calls.append(1), "answer")[1])
    brain = CachingBrain(inner)

    assert brain.think("same").content == "answer"
    assert brain.think("same").content == "answer"
    assert len(calls) == 1                 # inner called once
    assert brain.hits == 1 and brain.misses == 1


def test_different_prompts_miss():
    calls = []
    inner = MockBrain(reply_fn=lambda m: (calls.append(1), "x")[1])
    brain = CachingBrain(inner)
    brain.think("a")
    brain.think("b")
    assert len(calls) == 2 and brain.misses == 2 and brain.hits == 0


def test_system_is_part_of_the_key():
    inner = MockBrain(reply_fn=lambda m: "r")
    brain = CachingBrain(inner)
    brain.think("q", system="one")
    brain.think("q", system="two")
    assert brain.misses == 2               # same prompt, different system → distinct


def test_tool_turns_are_not_cached():
    inner = MockBrain(replies=[
        [ToolCall(id="1", name="t", arguments={})],
        [ToolCall(id="2", name="t", arguments={})],
    ])
    brain = CachingBrain(inner)
    from ormica.brain.tool import tool

    @tool
    def t() -> str:
        """t."""
        return "ok"

    r1 = brain.think("go", tools=[t])
    r2 = brain.think("go", tools=[t])
    assert r1.tool_calls and r2.tool_calls
    assert brain.hits == 0 and brain.misses == 0   # tool turns bypass the cache entirely


def test_lru_eviction_bounds_size():
    inner = MockBrain(reply_fn=lambda m: "r")
    brain = CachingBrain(inner, maxsize=2)
    brain.think("a")
    brain.think("b")
    brain.think("c")                       # evicts "a"
    assert len(brain._cache) == 2
    brain.think("a")                       # "a" was evicted → miss again
    assert brain.misses == 4


def test_name_wraps_inner():
    assert "caching" in CachingBrain(MockBrain(replies=["x"])).name
