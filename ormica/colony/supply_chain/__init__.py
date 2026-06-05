"""Supply-chain colony — procurement, warehouse, logistics, quality."""
from __future__ import annotations

from ormica.colony.base import AgentTemplate, Colony
from ormica.colony.registry import register


class ProcurementAgent(AgentTemplate):
    name = "procurement"
    role = "procurement"
    task = "Source materials and manage suppliers."
    system_prompt = (
        "You are the procurement lead. Source materials, negotiate with "
        "suppliers, manage purchase orders, and ensure on-time delivery."
    )


class WarehouseAgent(AgentTemplate):
    name = "warehouse"
    role = "warehouse"
    task = "Receive, store, and dispatch inventory."
    system_prompt = (
        "You are the warehouse lead. Receive deliveries, track inventory "
        "levels, and coordinate with logistics on outbound shipments."
    )


class LogisticsAgent(AgentTemplate):
    name = "logistics"
    role = "logistics"
    task = "Plan and execute shipments."
    system_prompt = (
        "You are the logistics lead. Plan shipping routes, manage carriers, "
        "track shipments, and resolve delivery issues."
    )


class QualityAgent(AgentTemplate):
    name = "quality"
    role = "quality"
    task = "Inspect goods and enforce quality standards."
    system_prompt = (
        "You are the quality lead. Inspect incoming and outgoing goods, "
        "flag defects, and enforce quality standards across the chain."
    )


@register
class SupplyChainColony(Colony):
    name = "supply_chain"
    description = "End-to-end supply chain — procurement, warehouse, logistics, quality."

    def templates(self) -> list[type[AgentTemplate]]:
        return [ProcurementAgent, WarehouseAgent, LogisticsAgent, QualityAgent]


__all__ = [
    "LogisticsAgent",
    "ProcurementAgent",
    "QualityAgent",
    "SupplyChainColony",
    "WarehouseAgent",
]
