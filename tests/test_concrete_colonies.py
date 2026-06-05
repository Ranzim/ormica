"""Tests for the bundled BusinessColony and SupplyChainColony content."""
from ormica import Ormica
from ormica.colony import AgentTemplate
from ormica.colony.business import (
    BusinessColony,
    FinanceAgent,
    MarketingAgent,
    OperationsAgent,
    SalesAgent,
)
from ormica.colony.supply_chain import (
    LogisticsAgent,
    ProcurementAgent,
    QualityAgent,
    SupplyChainColony,
    WarehouseAgent,
)


def test_business_templates_are_all_agent_templates():
    for tmpl in (OperationsAgent, SalesAgent, MarketingAgent, FinanceAgent):
        assert issubclass(tmpl, AgentTemplate)
        assert tmpl.role  # role string set
        assert tmpl.system_prompt  # non-empty default prompt


def test_business_colony_plants_four_departments_with_roles():
    org = Ormica("Acme")
    nodes = BusinessColony().plant(org)

    by_role = {n.role: n for n in nodes}
    assert set(by_role) == {"operations", "sales", "marketing", "finance"}
    for node in nodes:
        assert node.meta["system_prompt"]
        assert node.task


def test_business_colony_plants_under_custom_parent():
    org = Ormica("Acme")
    division = org.spawn("us_west")
    nodes = BusinessColony().plant(org, under=division)
    for node in nodes:
        assert node.parent is division


def test_supply_chain_templates_are_all_agent_templates():
    for tmpl in (ProcurementAgent, WarehouseAgent, LogisticsAgent, QualityAgent):
        assert issubclass(tmpl, AgentTemplate)
        assert tmpl.role
        assert tmpl.system_prompt


def test_supply_chain_colony_plants_four_departments():
    org = Ormica("Globex")
    nodes = SupplyChainColony().plant(org)

    by_role = {n.role: n for n in nodes}
    assert set(by_role) == {"procurement", "warehouse", "logistics", "quality"}


def test_two_colonies_can_coexist_on_one_org():
    """Same org can host overlapping colonies — useful for "company with supply chain"."""
    org = Ormica("BigCo")
    org.plant("business")
    org.plant("supply_chain")

    # 1 root + 4 business + 4 supply_chain
    assert len(org) == 9
    org.find("sales")
    org.find("logistics")


def test_org_add_single_template_works_alongside_colony():
    org = Ormica("HQ")
    org.add(OperationsAgent)

    ops = org.find("operations")
    assert ops.role == "operations"
    assert ops.meta["template"] == "OperationsAgent"
