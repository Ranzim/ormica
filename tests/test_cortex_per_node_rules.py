"""Tests for per-node rule overrides (v0.2 step 3).

Rules can be attached to any ``Node`` via ``node.rules``. They cascade down
the tree: a rule on a department applies to every think / spawn under that
subtree; a rule on the root behaves like an org-wide Constitution.
"""
from __future__ import annotations

import pytest

from ormica import Agent, Ormica
from ormica.arbor import SpawnDenied
from ormica.brain import MockBrain
from ormica.cortex import Constitution, Rule, RuleViolation
from ormica.cortex.rules import (
    banned_words,
    block_role,
    max_depth,
    max_tokens,
)


# --- node.rules: basic shape --------------------------------------------------


def test_node_rules_defaults_to_empty_list():
    org = Ormica("HQ")
    node = org.spawn("scout")
    assert node.rules == []


def test_node_rules_field_is_mutable():
    """Smoke test: appending to node.rules works as expected."""
    org = Ormica("HQ")
    node = org.spawn("scout")
    rule = max_tokens(100)
    node.rules.append(rule)
    assert node.rules == [rule]


# --- pre-stage cascade --------------------------------------------------------


def test_pre_rule_on_node_fires_for_that_node():
    """A pre rule attached to a node fires when that node's agent thinks."""
    org = Ormica("HQ")
    scout = org.spawn("scout", role="scout")
    scout.rules.append(banned_words({"forbidden"}))
    # banned_words is post-stage; use a pre rule instead.
    scout.rules.clear()
    scout.rules.append(
        Rule(name="no_act", description="scout can't act",
             check=lambda _ctx: False, stage="pre"),
    )
    agent = Agent(scout, MockBrain(replies=["ok"]))

    with pytest.raises(RuleViolation):
        agent.act("look")


def test_pre_rule_on_node_does_not_fire_for_sibling():
    """A pre rule on node A must not affect node B (siblings)."""
    org = Ormica("HQ")
    scout = org.spawn("scout", role="scout")
    hunter = org.spawn("hunter", role="hunter")
    scout.rules.append(
        Rule(name="scout_locked", description="only scout is locked",
             check=lambda _ctx: False, stage="pre"),
    )

    # Hunter should be unaffected.
    hunter_agent = Agent(hunter, MockBrain(replies=["hunted"]))
    assert hunter_agent.act("hunt").content == "hunted"

    # Scout should be blocked.
    scout_agent = Agent(scout, MockBrain(replies=["scouted"]))
    with pytest.raises(RuleViolation):
        scout_agent.act("look")


def test_pre_rule_on_ancestor_cascades_to_descendant():
    """A pre rule on a parent applies to its child too (cascade)."""
    org = Ormica("HQ")
    sales = org.spawn("sales", role="sales")
    sales.rules.append(
        Rule(name="dept_lock", description="sales subtree is locked",
             check=lambda _ctx: False, stage="pre"),
    )
    rep = org.tree.spawn(sales, "rep", role="rep")

    agent = Agent(rep, MockBrain(replies=["report"]))
    with pytest.raises(RuleViolation):
        agent.act("report")


def test_pre_rule_on_root_behaves_like_org_wide():
    """A rule on the root applies to every node in the tree."""
    org = Ormica("HQ")
    org.root.rules.append(
        Rule(name="root_lock", description="nobody acts",
             check=lambda _ctx: False, stage="pre"),
    )
    for name in ("scout", "hunter"):
        node = org.spawn(name, role=name)
        agent = Agent(node, MockBrain(replies=["ok"]))
        with pytest.raises(RuleViolation):
            agent.act("hi")


def test_per_node_rule_works_with_no_org_constitution():
    """Per-node rules must fire even when Ormica was created without a Constitution."""
    org = Ormica("HQ")  # no constitution=
    assert org.constitution is None  # confirm baseline
    scout = org.spawn("scout", role="scout")
    scout.rules.append(
        Rule(name="block", description="blocked",
             check=lambda _ctx: False, stage="pre"),
    )

    agent = Agent(scout, MockBrain(replies=["x"]))
    with pytest.raises(RuleViolation):
        agent.act("hi")


def test_per_node_rule_composes_with_org_constitution():
    """Per-node rule + org Constitution rule both evaluated; either can deny."""
    constitution = Constitution([max_tokens(1_000_000)])  # passes
    org = Ormica("HQ", constitution=constitution)
    scout = org.spawn("scout", role="scout")
    scout.rules.append(
        Rule(name="node_block", description="node-level deny",
             check=lambda _ctx: False, stage="pre"),
    )
    agent = Agent(scout, MockBrain(replies=["x"]),
                  constitution=org.constitution)

    with pytest.raises(RuleViolation) as exc_info:
        agent.act("hi")
    # Confirm the failing rule was the node-attached one.
    names = [v.rule.name for v in exc_info.value.violations]
    assert "node_block" in names


# --- post-stage cascade -------------------------------------------------------


def test_post_rule_on_node_fires_for_that_node():
    """A post rule attached to a node fires after that node's brain.think."""
    org = Ormica("HQ")
    scout = org.spawn("scout", role="scout")
    scout.rules.append(banned_words({"secret"}))

    agent = Agent(scout, MockBrain(replies=["the secret formula"]))
    with pytest.raises(RuleViolation):
        agent.act("tell me")


def test_post_rule_on_node_does_not_fire_for_sibling():
    org = Ormica("HQ")
    scout = org.spawn("scout", role="scout")
    hunter = org.spawn("hunter", role="hunter")
    scout.rules.append(banned_words({"secret"}))

    hunter_agent = Agent(hunter, MockBrain(replies=["the secret stash"]))
    # Hunter is fine — the rule is attached to scout, not its sibling.
    assert hunter_agent.act("hunt").content == "the secret stash"


# --- spawn-stage cascade ------------------------------------------------------


def test_spawn_rule_on_node_blocks_spawns_in_subtree():
    """A spawn rule on a department blocks spawns under that department only."""
    org = Ormica("HQ")
    sales = org.spawn("sales", role="sales")
    sales.rules.append(max_depth(1))  # nothing past depth 1 under sales

    # Spawning a sibling at depth 1 elsewhere is fine.
    org.spawn("ops", role="ops")
    # Spawning under sales must succeed at the immediate child level (depth 2
    # relative to root, but the max_depth rule reads ctx["depth"] absolute) —
    # max_depth(1) measures depth from root, so this blocks depth 2 spawns.
    with pytest.raises(SpawnDenied):
        org.tree.spawn(sales, "rep", role="rep")


def test_spawn_rule_on_ancestor_does_not_affect_sibling_subtree():
    """A spawn rule on sales must not block spawns under ops."""
    org = Ormica("HQ")
    sales = org.spawn("sales", role="sales")
    ops = org.spawn("ops", role="ops")
    sales.rules.append(
        Rule(name="block_under_sales", description="no spawns under sales",
             check=lambda _ctx: False, stage="spawn"),
    )

    # ops is a sibling of sales — sales's rule must not apply.
    rep = org.tree.spawn(ops, "rep", role="rep")
    assert rep.name == "rep"


def test_per_node_spawn_rule_works_with_no_org_constitution():
    """Per-node spawn rules fire even when org has no Constitution."""
    org = Ormica("HQ")
    assert org.constitution is None
    sales = org.spawn("sales", role="sales")
    sales.rules.append(block_role("finance"))

    # Spawning a finance node under sales is now blocked.
    with pytest.raises(SpawnDenied):
        org.tree.spawn(sales, "treasury", role="finance")


def test_block_role_on_root_acts_like_org_wide_rule():
    """Attaching block_role to the root is equivalent to an org Constitution."""
    org = Ormica("HQ")
    org.root.rules.append(block_role("finance"))

    org.spawn("ops", role="ops")  # ok
    with pytest.raises(SpawnDenied):
        org.spawn("treasury", role="finance")


# --- runtime integration ------------------------------------------------------


def test_run_loop_marks_only_constrained_node_failed():
    """One sibling has a rule that fails; the other doesn't. Run keeps going."""
    org = Ormica("HQ")
    scout = org.spawn("scout", role="scout")
    org.spawn("hunter", role="hunter")
    scout.rules.append(banned_words({"forbidden"}))
    org.task("scout", dept="scout")
    org.task("hunt", dept="hunter")

    result = org.run(brain=MockBrain(replies=["the forbidden thing", "all clear"]))

    assert result.processed == 2
    assert result.succeeded == 1
    assert result.failed == 1
    by_target = {t.target: t for t in org.tasks}
    assert by_target["hunter"].status == "done"
    assert by_target["scout"].status == "failed"
