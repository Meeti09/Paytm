"""Deterministic policy / risk engine.

This module is the autonomy boundary. The LLM may *propose* an action; it never
decides whether the action is permitted. Every proposal is evaluated here by
plain, auditable Python rules — no model call, no probability, no override.

The thresholds below are a HACKATHON DEMO POLICY. They are not a statement about
Paytm's real production policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import settings

Verdict = Literal["AUTONOMOUS", "REQUIRES_APPROVAL"]
RiskLevel = Literal["low", "medium", "high"]


class PolicyRule:
    MONEY_MOVEMENT_THRESHOLD = "MONEY_MOVEMENT_THRESHOLD"
    ACCOUNT_LEVEL_ACTION = "ACCOUNT_LEVEL_ACTION"
    NEGATIVE_SENTIMENT_REVIEW = "NEGATIVE_SENTIMENT_REVIEW"
    IRREVERSIBLE_ACTION = "IRREVERSIBLE_ACTION"
    PERMISSION_BOUNDARY = "PERMISSION_BOUNDARY"
    WITHIN_AUTONOMY = "WITHIN_AUTONOMY"


NEGATIVE_SENTIMENTS = {"strongly_negative", "angry"}


@dataclass
class ActionProposal:
    """What an agent wants to do. Produced by the agent, judged by this engine."""

    action_type: str
    description: str
    subject: str = ""
    money_amount: float = 0.0
    affects_account: bool = False
    irreversible: bool = False
    sentiment: str = "neutral"
    customer_facing: bool = False
    authorized: bool = True
    permission_note: str = ""
    evidence: list[str] = field(default_factory=list)
    impact: str = ""
    ai_recommendation: str = "APPROVE"
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class TriggeredRule:
    rule: str
    detail: str
    risk: RiskLevel


@dataclass
class RiskDecision:
    verdict: Verdict
    risk_level: RiskLevel
    primary_rule: str
    reason: str
    policy_detail: str
    triggered: list[TriggeredRule] = field(default_factory=list)

    @property
    def requires_approval(self) -> bool:
        return self.verdict == "REQUIRES_APPROVAL"

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "risk_level": self.risk_level,
            "primary_rule": self.primary_rule,
            "reason": self.reason,
            "policy_detail": self.policy_detail,
            "triggered": [
                {"rule": t.rule, "detail": t.detail, "risk": t.risk}
                for t in self.triggered
            ],
        }


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _inr(amount: float) -> str:
    return f"₹{amount:,.0f}"


def evaluate_action(proposal: ActionProposal) -> RiskDecision:
    """Evaluate a proposed action against the autonomy policy.

    Deterministic and side-effect free. Returns every rule that fired so the
    Approval Queue can explain exactly why the agent stopped.
    """
    triggered: list[TriggeredRule] = []
    threshold = settings.refund_approval_threshold

    # Rule 1 — money movement above the configured threshold.
    if proposal.money_amount > threshold:
        triggered.append(
            TriggeredRule(
                rule=PolicyRule.MONEY_MOVEMENT_THRESHOLD,
                detail=(
                    f"{_inr(proposal.money_amount)} exceeds the "
                    f"{_inr(threshold)} autonomous money-movement limit."
                ),
                risk="high",
            )
        )

    # Rule 2 — account-level actions.
    if proposal.affects_account and settings.account_actions_require_approval:
        triggered.append(
            TriggeredRule(
                rule=PolicyRule.ACCOUNT_LEVEL_ACTION,
                detail="Action changes account-level state.",
                risk="high",
            )
        )

    # Rule 3 — strong negative sentiment on a customer-facing action.
    # Workflow routing only. This is not a psychological assessment.
    if (
        settings.negative_sentiment_requires_review
        and proposal.sentiment in NEGATIVE_SENTIMENTS
    ):
        triggered.append(
            TriggeredRule(
                rule=PolicyRule.NEGATIVE_SENTIMENT_REVIEW,
                detail=(
                    "Conversation sentiment classified as strongly negative; "
                    "customer-facing actions are routed for human review."
                ),
                risk="medium",
            )
        )

    # Rule 4 — irreversible actions.
    if proposal.irreversible and settings.irreversible_actions_require_approval:
        triggered.append(
            TriggeredRule(
                rule=PolicyRule.IRREVERSIBLE_ACTION,
                detail="Action cannot be automatically reversed once executed.",
                risk="high",
            )
        )

    # Rule 5 — outside the agent's declared permissions.
    if not proposal.authorized and settings.unknown_permissions_require_approval:
        triggered.append(
            TriggeredRule(
                rule=PolicyRule.PERMISSION_BOUNDARY,
                detail=proposal.permission_note
                or "Agent is not authorized to execute this action type.",
                risk="high",
            )
        )

    if not triggered:
        risk: RiskLevel = "medium" if proposal.money_amount > 0 else "low"
        return RiskDecision(
            verdict="AUTONOMOUS",
            risk_level=risk,
            primary_rule=PolicyRule.WITHIN_AUTONOMY,
            reason="Action is inside the agent's autonomous envelope.",
            policy_detail=(
                f"Money movement of {_inr(proposal.money_amount)} is at or below the "
                f"{_inr(threshold)} autonomous limit."
                if proposal.money_amount > 0
                else "No money movement, no account change, reversible action."
            ),
        )

    triggered.sort(key=lambda t: _RISK_ORDER[t.risk], reverse=True)
    primary = triggered[0]
    return RiskDecision(
        verdict="REQUIRES_APPROVAL",
        risk_level=primary.risk,
        primary_rule=primary.rule,
        reason=primary.detail,
        policy_detail=" ".join(t.detail for t in triggered),
        triggered=triggered,
    )


def current_policy() -> dict[str, Any]:
    """The live policy, rendered on the Approval Queue banner."""
    threshold = settings.refund_approval_threshold
    return {
        "refund_threshold": threshold,
        "refund_threshold_label": _inr(threshold),
        "account_actions_require_approval": settings.account_actions_require_approval,
        "negative_sentiment_requires_review": settings.negative_sentiment_requires_review,
        "irreversible_actions_require_approval": settings.irreversible_actions_require_approval,
        "unknown_permissions_require_approval": settings.unknown_permissions_require_approval,
        "disclaimer": (
            "Hackathon demo policy. Not Paytm's production policy. "
            "Configurable via REFUND_APPROVAL_THRESHOLD."
        ),
        "rules": [
            {
                "rule": PolicyRule.MONEY_MOVEMENT_THRESHOLD,
                "label": f"Money movement above {_inr(threshold)}",
                "enabled": True,
            },
            {
                "rule": PolicyRule.ACCOUNT_LEVEL_ACTION,
                "label": "Account-level actions",
                "enabled": settings.account_actions_require_approval,
            },
            {
                "rule": PolicyRule.NEGATIVE_SENTIMENT_REVIEW,
                "label": "Strong negative customer sentiment",
                "enabled": settings.negative_sentiment_requires_review,
            },
            {
                "rule": PolicyRule.IRREVERSIBLE_ACTION,
                "label": "Irreversible external actions",
                "enabled": settings.irreversible_actions_require_approval,
            },
            {
                "rule": PolicyRule.PERMISSION_BOUNDARY,
                "label": "Actions outside agent permissions",
                "enabled": settings.unknown_permissions_require_approval,
            },
        ],
        "autonomous": [
            "Read customer, transaction and merchant records",
            "Retrieve policy and support history",
            "Classify intent and language",
            "Score and rank leads",
            "Draft outreach and responses",
            f"Refunds at or below {_inr(threshold)}",
            "Send low-risk notifications",
        ],
    }
