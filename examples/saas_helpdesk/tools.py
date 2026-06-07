"""Tools the helpdesk agents can call.

In production you'd swap each of these for the real call — Stripe API,
your customer DB, your email provider. Here they're mocked so the
example runs offline with deterministic output.
"""
from __future__ import annotations

from dataclasses import dataclass

from ormica.brain import tool


@dataclass
class Customer:
    id: str
    name: str
    plan: str
    monthly_revenue_usd: int
    refund_eligible: bool


# A tiny in-memory "CRM" so lookup_customer has something to return.
_CUSTOMERS: dict[str, Customer] = {
    "acme-cust-001": Customer("acme-cust-001", "Acme Inc.", "Growth", 499, refund_eligible=False),
    "acme-cust-042": Customer("acme-cust-042", "Globex Co.", "Scale", 2_499, refund_eligible=True),
    "acme-cust-088": Customer("acme-cust-088", "Initech LLC", "Enterprise", 12_000, refund_eligible=True),
}


@tool
def lookup_customer(customer_id: str) -> str:
    """Look up customer details by id. Returns a single-line summary."""
    c = _CUSTOMERS.get(customer_id)
    if c is None:
        return f"not found: {customer_id}"
    elig = "yes" if c.refund_eligible else "no"
    return (
        f"{c.id}: {c.name} | plan={c.plan} | mrr=${c.monthly_revenue_usd} "
        f"| refund_eligible={elig}"
    )


@tool
def get_subscription_status(customer_id: str) -> str:
    """Return the subscription status string for a customer."""
    c = _CUSTOMERS.get(customer_id)
    if c is None:
        return "unknown"
    return f"{c.plan} (active)"


@tool
def send_email(to: str, subject: str, body: str) -> str:  # noqa: ARG001
    """Send an outbound email (mocked — just records the intent)."""
    return f"queued email to {to}, subject={subject!r}"


@tool
def escalate_to_human(ticket_id: str, reason: str) -> str:
    """Mark a ticket for human follow-up with a reason."""
    return f"ticket {ticket_id} escalated, reason: {reason}"


@tool
def create_internal_note(ticket_id: str, note: str) -> str:
    """Attach an internal note to a ticket."""
    return f"note added to {ticket_id}: {note}"


def all_tools() -> list:
    """Return every helpdesk tool, ready to pass to ``Agent.act_with_tools``."""
    return [
        lookup_customer,
        get_subscription_status,
        send_email,
        escalate_to_human,
        create_internal_note,
    ]
