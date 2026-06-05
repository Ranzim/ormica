"""Business colony — operations, sales, marketing, finance."""
from __future__ import annotations

from ormica.colony.base import AgentTemplate, Colony
from ormica.colony.registry import register


class OperationsAgent(AgentTemplate):
    name = "operations"
    role = "operations"
    task = "Keep day-to-day business operations running smoothly."
    system_prompt = (
        "You are the operations lead. Identify operational issues, "
        "propose solutions, and coordinate with other departments to "
        "keep the business running."
    )


class SalesAgent(AgentTemplate):
    name = "sales"
    role = "sales"
    task = "Find qualified leads and close deals."
    system_prompt = (
        "You are the sales lead. Identify qualified leads, follow up "
        "with prospects, and close deals. Coordinate with marketing "
        "on warm inbound leads."
    )


class MarketingAgent(AgentTemplate):
    name = "marketing"
    role = "marketing"
    task = "Generate awareness and qualified interest."
    system_prompt = (
        "You are the marketing lead. Plan campaigns, produce content, "
        "and feed qualified leads to sales."
    )


class FinanceAgent(AgentTemplate):
    name = "finance"
    role = "finance"
    task = "Track cash flow, budgets, and financial reporting."
    system_prompt = (
        "You are the finance lead. Track spend, forecast cash flow, "
        "flag anomalies, and produce reports."
    )


@register
class BusinessColony(Colony):
    name = "business"
    description = "Generic business — operations, sales, marketing, finance."

    def templates(self) -> list[type[AgentTemplate]]:
        return [OperationsAgent, SalesAgent, MarketingAgent, FinanceAgent]


__all__ = [
    "BusinessColony",
    "FinanceAgent",
    "MarketingAgent",
    "OperationsAgent",
    "SalesAgent",
]
