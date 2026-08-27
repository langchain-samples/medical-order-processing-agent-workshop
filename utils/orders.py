"""Synthetic order records + a lookup helper for the order operations agent.

The shape mirrors `utils/search.py`: keep the data and the plumbing here, and
expose a thin `@tool` at the call site in `agent.py` so the tool's name,
docstring, and signature stay visible to the reader.

    from langchain_core.tools import tool
    from utils.orders import lookup_order

    @tool(parse_docstring=True)
    def order_lookup(order_id: str) -> str:
        \"\"\"Look up the current status of a device order by its order ID.

        Args:
            order_id: The order identifier, e.g. "ORD-10432".
        \"\"\"
        return lookup_order(order_id)

All records below are SYNTHETIC — no real patients, accounts, or member data.
Fields deliberately avoid patient identifiers, member IDs, and full dates of
birth, consistent with the agent's rules in AGENTS.md.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Synthetic order book. Each record is what the order desk can see internally.
# `status` is the workflow state; `blocker` explains any hold in plain terms.
# --------------------------------------------------------------------------- #

ORDERS: dict[str, dict] = {
    "ORD-10432": {
        "order_id": "ORD-10432",
        "account": "Cedar Valley Home Health",
        "device": "Continuous Glucose Monitor (CGM)",
        "hcpcs": "E2103",
        "payer": "Medicare Part B (DME MAC)",
        "status": "Pending prior authorization",
        "ordered_on": "2025-01-06",
        "expected_ship": None,
        "blocker": "Awaiting prior authorization decision; submitted 2025-01-08.",
        "last_update": "2025-01-14",
    },
    "ORD-10518": {
        "order_id": "ORD-10518",
        "account": "Riverside Physical Therapy",
        "device": "Ambulatory Infusion Pump",
        "hcpcs": "E0781",
        "payer": "Aetna Commercial PPO",
        "status": "On hold — documentation needed",
        "ordered_on": "2025-01-09",
        "expected_ship": None,
        "blocker": (
            "Certificate of Medical Necessity (CMN) is missing the clinician "
            "signature and expected length of need."
        ),
        "last_update": "2025-01-15",
    },
    "ORD-10627": {
        "order_id": "ORD-10627",
        "account": "Summit Orthopedics Group",
        "device": "Bi-Level Positive Airway Pressure (BiPAP)",
        "hcpcs": "E0470",
        "payer": "UnitedHealthcare Medicare Advantage",
        "status": "Approved — scheduled to ship",
        "ordered_on": "2025-01-03",
        "expected_ship": "2025-01-17",
        "blocker": None,
        "last_update": "2025-01-15",
    },
    "ORD-10711": {
        "order_id": "ORD-10711",
        "account": "Lakeside Family Medicine",
        "device": "Manual Wheelchair",
        "hcpcs": "K0001",
        "payer": "BCBS Commercial HMO",
        "status": "Denied — appeal in progress",
        "ordered_on": "2024-12-20",
        "expected_ship": None,
        "blocker": (
            "Initial claim denied for insufficient medical-necessity "
            "documentation; appeal submitted with updated chart notes."
        ),
        "last_update": "2025-01-13",
    },
    "ORD-10809": {
        "order_id": "ORD-10809",
        "account": "Cedar Valley Home Health",
        "device": "Hospital Bed (semi-electric)",
        "hcpcs": "E0260",
        "payer": "Medicaid (state plan)",
        "status": "Delivered",
        "ordered_on": "2024-12-28",
        "expected_ship": "2025-01-06",
        "blocker": None,
        "last_update": "2025-01-07",
    },
}


def _format_order(o: dict) -> str:
    """Render one order record as a readable block for the agent to reason over."""
    lines = [
        f"Order {o['order_id']} — {o['status']}",
        f"  Account:       {o['account']}",
        f"  Device:        {o['device']} (HCPCS {o['hcpcs']})",
        f"  Payer:         {o['payer']}",
        f"  Ordered on:    {o['ordered_on']}",
        f"  Expected ship: {o['expected_ship'] or 'not yet scheduled'}",
        f"  Blocker:       {o['blocker'] or 'none'}",
        f"  Last updated:  {o['last_update']}",
    ]
    return "\n".join(lines)


def lookup_order(order_id: str) -> str:
    """Return a formatted status block for `order_id`, or a not-found message.

    The match is case-insensitive and tolerant of surrounding whitespace. If the
    caller passes a bare number (e.g. "10432"), we try the "ORD-" prefix too.
    """
    if not order_id or not order_id.strip():
        return (
            "No order ID provided. Ask the requester for the order number "
            "(format: ORD-#####)."
        )

    key = order_id.strip().upper()
    order = ORDERS.get(key)
    if order is None and not key.startswith("ORD-") and key.isdigit():
        order = ORDERS.get(f"ORD-{key}")

    if order is None:
        known = ", ".join(sorted(ORDERS))
        return (
            f"No order found matching '{order_id}'. "
            f"Known synthetic order IDs: {known}."
        )

    return _format_order(order)


def list_orders() -> str:
    """Return a one-line summary of every order in the synthetic order book."""
    return "\n".join(
        f"{o['order_id']}: {o['device']} — {o['status']} ({o['account']})"
        for o in ORDERS.values()
    )
