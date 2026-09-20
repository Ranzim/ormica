"""Tests for recursive delegation — an agent spawning a sub-colony."""
from ormica import Ormica
from ormica.brain import MockBrain, ToolCall
from ormica.canopy import BudgetGovernor


def _delegating_brain(plan: dict):
    """A brain that delegates per `plan` (task text → subtasks) else answers plainly.

    On a post-tool turn (a delegate result is in history) it synthesises.
    """
    def reply(messages):
        if any(m.role == "tool" for m in messages):
            out = [m for m in messages if m.role == "tool"][-1].content
            return "SYNTH(" + out.replace("\n", " | ") + ")"
        text = messages[-1].content.strip()
        subs = plan.get(text)
        if subs:
            return [ToolCall(id="d", name="delegate", arguments={"subtasks": subs})]
        return f"{text} solved"
    return MockBrain(reply_fn=reply)


def _count(org, role):
    return sum(1 for n in org if n.role == role)


# --- one level ----------------------------------------------------------------


def test_delegates_and_spawns_subagents():
    org = Ormica("Acme")
    brain = _delegating_brain({"big goal": ["do A", "do B"]})
    resp = org.solve("big goal", brain=brain, max_depth=2)
    assert _count(org, "delegate") == 2                 # two sub-agents spawned
    assert "do A solved" in resp.content and "do B solved" in resp.content
    assert resp.content.startswith("SYNTH(")            # parent synthesised results


def test_no_delegation_when_model_answers_directly():
    org = Ormica("Acme")
    brain = _delegating_brain({})                        # never delegates
    resp = org.solve("simple", brain=brain, max_depth=2)
    assert resp.content == "simple solved"
    assert _count(org, "delegate") == 0


# --- recursion + depth bound --------------------------------------------------


def test_recursion_goes_deep_then_stops_at_max_depth():
    org = Ormica("Lab", max_depth=8)
    # root goal → "mid"; "mid" would delegate → "leaf"; "leaf" answers.
    brain = _delegating_brain({"root goal": ["mid"], "mid": ["leaf"]})
    org.solve("root goal", brain=brain, max_depth=2)
    # depth 0 (root agent) delegates → child "mid" at depth 1 gets a delegate
    # tool (1<2) and delegates → grandchild "leaf" at depth 2 gets NO delegate
    # tool (2<2 is false) so it answers directly. Deepest node is depth 2.
    depths = [n.depth for n in org if n.role == "delegate"]
    assert max(depths) == 2                              # recursion bounded at max_depth


def test_depth_one_children_cannot_delegate_further():
    org = Ormica("Lab", max_depth=8)
    brain = _delegating_brain({"g": ["mid"], "mid": ["leaf"]})
    org.solve("g", brain=brain, max_depth=1)
    # max_depth=1 → the parent itself gets delegate, but its children do not,
    # so "mid" answers directly and never spawns "leaf".
    assert _count(org, "delegate") == 1


# --- fan-out + governor bounds ------------------------------------------------


def test_max_subtasks_caps_fanout():
    org = Ormica("Acme")
    brain = _delegating_brain({"g": ["a", "b", "c", "d", "e"]})
    org.solve("g", brain=brain, max_depth=2, max_subtasks=2)
    assert _count(org, "delegate") == 2                 # only first 2 spawned


def test_governor_stops_runaway_delegation():
    # root + 1 allowed spawn = 2 nodes; the 2nd subtask spawn is denied.
    org = Ormica("Acme", spawn_governor=BudgetGovernor(max_agents=2))
    brain = _delegating_brain({"g": ["a", "b"]})
    resp = org.solve("g", brain=brain, max_depth=2)
    assert _count(org, "delegate") == 1                 # governor capped growth
    assert "not spawned" in resp.content                # reported, not fatal
