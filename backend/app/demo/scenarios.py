"""Deterministic demo scenarios.

Three Resolve scenarios that exercise the three interesting policy paths, and one
Grow objective. Each carries only a customer and a message — the agent discovers
the transaction itself, exactly as it would from a real inbound message.
"""

from __future__ import annotations

RESOLVE_SCENARIOS: list[dict] = [
    {
        "id": "A",
        "title": "Autonomous resolution",
        "customer_id": "CUST-002",
        "customer_name": "Neha Kulkarni",
        "message": (
            "₹500 was debited from my account but the shop says they did not "
            "receive it. Please check."
        ),
        "language": "English",
        "expected": "Refund ₹500 — inside the ₹1,000 autonomous limit",
        "expected_outcome": "Resolved autonomously",
    },
    {
        "id": "B",
        "title": "Human approval required",
        "customer_id": "CUST-001",
        "customer_name": "Aarav Shah",
        "message": "₹2,000 कट गया लेकिन merchant को नहीं मिला.",
        "language": "Hindi",
        "expected": "Refund ₹2,000 — above the ₹1,000 limit",
        "expected_outcome": "Escalated to the Approval Queue",
    },
    {
        "id": "C",
        "title": "Sentiment escalation",
        "customer_id": "CUST-003",
        "customer_name": "Imran Shaikh",
        "message": "तीन बार शिकायत कर चुका हूँ, अभी तक पैसे वापस नहीं आए!",
        "language": "Hindi",
        "expected": (
            "₹800 refund — under the limit, but strongly negative sentiment "
            "routes it to a human"
        ),
        "expected_outcome": "Escalated to the Approval Queue",
    },
]

GROW_SCENARIO = {
    "location": "Thane",
    "target_count": 5,
    "objective": "Find 5 high-potential merchants in Thane",
}


def resolve_scenario(scenario_id: str) -> dict | None:
    for scenario in RESOLVE_SCENARIOS:
        if scenario["id"].upper() == scenario_id.upper():
            return scenario
    return None
