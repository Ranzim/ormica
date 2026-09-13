"""Tests for the spawn-time budget/cost governor."""
import pytest

from ormica import Ormica
from ormica.arbor import Tree
from ormica.arbor.exceptions import SpawnDenied
from ormica.brain import MockBrain, TokenBudget
from ormica.canopy import BudgetGovernor


class _DenyPolicy:
    def allow(self, parent, child_name, *, role="", task=""):  # noqa: ARG002
        return False


class _AllowPolicy:
    def allow(self, parent, child_name, *, role="", task=""):  # noqa: ARG002
        return True


# --- unit: ceilings -----------------------------------------------------------


def test_max_agents_caps_tree_size():
    gov = BudgetGovernor(max_agents=3)
    tree = Tree("HQ", policy=gov)  # root counts as 1
    a = tree.spawn(tree.root, "a")  # 2
    tree.spawn(a, "b")              # 3
    with pytest.raises(SpawnDenied):
        tree.spawn(tree.root, "c")  # would be 4
    assert "max_agents=3" in gov.last_denial


def test_max_spawns_caps_cumulative_growth():
    gov = BudgetGovernor(max_spawns=2)
    tree = Tree("HQ", policy=gov)
    tree.spawn(tree.root, "a")
    tree.spawn(tree.root, "b")
    with pytest.raises(SpawnDenied):
        tree.spawn(tree.root, "c")
    assert gov.approved == 2
    assert "max_spawns=2" in gov.last_denial


def test_budget_reserve_blocks_spawn_when_low():
    budget = TokenBudget(limit=100, used=95)
    gov = BudgetGovernor(budget=budget, reserve_tokens=10)  # remaining 5 <= 10
    tree = Tree("HQ", policy=gov)
    with pytest.raises(SpawnDenied):
        tree.spawn(tree.root, "a")
    assert "budget too low" in gov.last_denial


def test_budget_allows_spawn_when_funded():
    budget = TokenBudget(limit=100, used=0)
    gov = BudgetGovernor(budget=budget, reserve_tokens=10)
    tree = Tree("HQ", policy=gov)
    assert tree.spawn(tree.root, "a") is not None  # remaining 100 > 10


def test_inner_policy_chained():
    gov = BudgetGovernor(max_agents=100, inner=_DenyPolicy())
    tree = Tree("HQ", policy=gov)
    with pytest.raises(SpawnDenied):
        tree.spawn(tree.root, "a")
    assert gov.last_denial == "inner policy denied"


def test_approved_counter_and_allow():
    gov = BudgetGovernor(inner=_AllowPolicy())
    tree = Tree("HQ", policy=gov)
    tree.spawn(tree.root, "a")
    tree.spawn(tree.root, "b")
    assert gov.approved == 2


# --- facade wiring ------------------------------------------------------------


def test_ormica_spawn_governor_caps_growth():
    org = Ormica("Acme", spawn_governor=BudgetGovernor(max_agents=2))
    org.spawn("sales")  # 2 nodes now (root + sales)
    with pytest.raises(SpawnDenied):
        org.spawn("eng")


def test_ormica_governor_composes_with_constitution():
    from ormica.cortex import Constitution
    from ormica.cortex.rules import block_role

    con = Constitution([block_role("hacker")])
    org = Ormica(
        "Acme", constitution=con, spawn_governor=BudgetGovernor(max_agents=10)
    )
    # Constitution rule still enforced under the governor composition.
    with pytest.raises(SpawnDenied):
        org.spawn("x", role="hacker")
    # A normal spawn is allowed.
    assert org.spawn("sales") is not None


# --- shared budget: runtime enforcement ---------------------------------------


def test_shared_budget_exhausts_across_tasks():
    budget = TokenBudget(limit=1)  # tiny
    org = Ormica("Acme", budget=budget)
    org.task("first")
    org.task("second")
    # MockBrain reply "xxxxxxxx" -> tokens_used = 8//4 = 2, exhausts after task 1.
    result = org.run(brain=MockBrain(replies=["xxxxxxxx"]))
    assert result.succeeded == 1
    assert result.failed == 1
    assert budget.used >= 1  # spend accumulated on the shared budget


def test_governor_denies_spawn_once_shared_budget_spent():
    budget = TokenBudget(limit=10, used=10)  # fully spent
    org = Ormica(
        "Acme",
        budget=budget,
        spawn_governor=BudgetGovernor(budget=budget),
    )
    with pytest.raises(SpawnDenied):
        org.spawn("sales")
