"""Agent tool permission model (Architecture.md §34).

Each teammate declares exactly which tools it may call and at what trust level.
The tool layer refuses anything outside that declaration, and any action type the
system does not recognise is treated as unauthorised — which the risk engine then
routes to a human. This is the guard against an LLM inventing a capability.
"""

from __future__ import annotations

from typing import Literal

TrustLevel = Literal["read", "write", "controlled"]


class ToolPermissionError(PermissionError):
    """Raised when an agent calls a tool it has not declared."""


# tool name -> trust level, per agent
AGENT_TOOLS: dict[str, dict[str, TrustLevel]] = {
    "resolve": {
        # READ
        "get_customer": "read",
        "get_transaction": "read",
        "get_merchant": "read",
        "get_policy": "read",
        "get_customer_history": "read",
        "get_memory": "read",
        "verify_refund": "read",
        # WRITE
        "create_case": "write",
        "send_customer_notification": "write",
        # CONTROLLED
        "request_refund": "controlled",
        "account_action": "controlled",
    },
    "grow": {
        # READ
        "search_demo_merchants": "read",
        "get_merchant_profile": "read",
        "get_paytm_status": "read",
        "get_memory": "read",
        # WRITE
        "score_lead": "write",
        "generate_outreach": "write",
        "update_lead": "write",
        "process_reply": "write",
        "book_meeting": "write",
        # CONTROLLED
        "send_outreach": "controlled",
    },
}

# action_type -> (agent, tool it maps to, human label)
ACTION_CATALOGUE: dict[str, tuple[str, str, str]] = {
    "refund": ("resolve", "request_refund", "Refund"),
    "notify_customer": ("resolve", "send_customer_notification", "Notify customer"),
    "create_case": ("resolve", "create_case", "Create support case"),
    "escalate_to_specialist": ("resolve", "create_case", "Escalate to specialist"),
    "account_action": ("resolve", "account_action", "Account-level action"),
    "send_outreach": ("grow", "send_outreach", "Send merchant outreach"),
    "book_meeting": ("grow", "book_meeting", "Book onboarding meeting"),
    "update_lead": ("grow", "update_lead", "Update lead"),
}


def has_tool(agent: str, tool: str) -> bool:
    return tool in AGENT_TOOLS.get(agent, {})


def trust_level(agent: str, tool: str) -> TrustLevel | None:
    return AGENT_TOOLS.get(agent, {}).get(tool)


def require_tool(agent: str, tool: str) -> TrustLevel:
    """Hard gate used by the tool layer before any tool executes."""
    level = trust_level(agent, tool)
    if level is None:
        raise ToolPermissionError(
            f"Agent '{agent}' is not permitted to call tool '{tool}'."
        )
    return level


def authorize_action(agent: str, action_type: str) -> tuple[bool, str]:
    """Is `agent` allowed to propose `action_type` at all?

    Returns (authorized, note). An unauthorized action is not blocked outright —
    it is handed to the risk engine, which routes it to a human. That keeps an
    unexpected model proposal visible instead of silently dropped.
    """
    entry = ACTION_CATALOGUE.get(action_type)
    if entry is None:
        return False, (
            f"'{action_type}' is not a recognised action type in the action catalogue."
        )
    owner, tool, _label = entry
    if owner != agent:
        return False, f"Action '{action_type}' belongs to the {owner} teammate."
    if not has_tool(agent, tool):
        return False, f"Agent '{agent}' has no '{tool}' permission."
    return True, ""


def action_label(action_type: str) -> str:
    entry = ACTION_CATALOGUE.get(action_type)
    return entry[2] if entry else action_type.replace("_", " ").title()


def permissions_summary() -> dict[str, dict[str, list[str]]]:
    summary: dict[str, dict[str, list[str]]] = {}
    for agent, tools in AGENT_TOOLS.items():
        grouped: dict[str, list[str]] = {"read": [], "write": [], "controlled": []}
        for tool, level in tools.items():
            grouped[level].append(tool)
        summary[agent] = grouped
    return summary
