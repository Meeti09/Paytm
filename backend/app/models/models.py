"""Paytm Pulse domain model.

Mission is the core object. Everything an agent does produces an Action, an
Approval (when policy demands one) and a stream of MissionEvents. Outcomes are
aggregated from these records — never hardcoded.

All customer / merchant / transaction rows are fictional demo data.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Simulated Paytm-side records (demo data)
# ---------------------------------------------------------------------------


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8), default="en")
    segment: Mapped[str] = mapped_column(String(32), default="retail")
    joined_on: Mapped[str] = mapped_column(String(24), default="")


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(48))
    location: Mapped[str] = mapped_column(String(80))
    # active | not_onboarded
    paytm_status: Mapped[str] = mapped_column(String(24), default="not_onboarded")
    estimated_volume: Mapped[int] = mapped_column(Integer, default=0)
    contact: Mapped[str] = mapped_column(String(80), default="")
    website: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.id"))
    merchant_id: Mapped[str] = mapped_column(String(32), ForeignKey("merchants.id"))
    amount: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String(24), default="UPI")
    # success | debited_not_settled | pending | failed | refunded
    status: Mapped[str] = mapped_column(String(32), default="success")
    settlement_status: Mapped[str] = mapped_column(String(32), default="settled")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SupportCase(Base):
    __tablename__ = "support_cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), ForeignKey("customers.id"))
    transaction_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    issue: Mapped[str] = mapped_column(Text, default="")
    sentiment: Mapped[str] = mapped_column(String(32), default="neutral")
    # open | reopened | resolved | with_specialist
    status: Mapped[str] = mapped_column(String(32), default="open")
    assigned_agent: Mapped[str] = mapped_column(String(32), default="resolve")
    resolution: Mapped[str] = mapped_column(Text, default="")
    mission_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mission_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    merchant_id: Mapped[str] = mapped_column(String(32), ForeignKey("merchants.id"))
    score: Mapped[int] = mapped_column(Integer, default=0)
    # discovered | scored | qualified | contacted | responded | sales_ready | meeting_booked | disqualified
    stage: Mapped[str] = mapped_column(String(32), default="discovered")
    stage_rank: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[list] = mapped_column(JSON, default=list)
    score_breakdown: Mapped[list] = mapped_column(JSON, default=list)
    next_action: Mapped[str] = mapped_column(String(160), default="")
    outreach_message: Mapped[str] = mapped_column(Text, default="")
    outreach_channel: Mapped[str] = mapped_column(String(32), default="")
    response_message: Mapped[str] = mapped_column(Text, default="")
    qualification_note: Mapped[str] = mapped_column(Text, default="")
    meeting_slot: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Mission core
# ---------------------------------------------------------------------------


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    agent: Mapped[str] = mapped_column(String(16))  # resolve | grow
    objective: Mapped[str] = mapped_column(Text)
    # created | running | waiting_approval | waiting_response | paused
    # | needs_attention | human_takeover | completed | failed
    status: Mapped[str] = mapped_column(String(32), default="created")
    # Fine-grained agent state-machine state, e.g. UNDERSTANDING, RISK_CHECK
    stage: Mapped[str] = mapped_column(String(32), default="MISSION_CREATED")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    # resolved_autonomously | resolved_with_approval | rejected_by_human
    # | handled_by_human | meeting_booked | no_qualified_leads | failed
    result: Mapped[str | None] = mapped_column(String(48), nullable=True)
    result_label: Mapped[str] = mapped_column(String(160), default="")
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    human_involved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mission_id: Mapped[str] = mapped_column(String(48), ForeignKey("missions.id"))
    action_type: Mapped[str] = mapped_column(String(48))
    description: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # proposed | pending_approval | executing | executed | verified | failed | cancelled
    status: Mapped[str] = mapped_column(String(24), default="proposed")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    executed_via: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mission_id: Mapped[str] = mapped_column(String(48), ForeignKey("missions.id"))
    action_id: Mapped[str] = mapped_column(String(32), ForeignKey("actions.id"))
    agent: Mapped[str] = mapped_column(String(16), default="resolve")
    title: Mapped[str] = mapped_column(String(160), default="")
    subject: Mapped[str] = mapped_column(String(160), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    policy_rule: Mapped[str] = mapped_column(String(48), default="")
    policy_detail: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str] = mapped_column(String(16), default="high")
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    triggered_rules: Mapped[list] = mapped_column(JSON, default=list)
    ai_recommendation: Mapped[str] = mapped_column(String(32), default="APPROVE")
    impact: Mapped[str] = mapped_column(Text, default="")
    # pending | approved | rejected | taken_over
    status: Mapped[str] = mapped_column(String(24), default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MissionEvent(Base):
    __tablename__ = "mission_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(String(48), ForeignKey("missions.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    event_type: Mapped[str] = mapped_column(String(48))
    actor: Mapped[str] = mapped_column(String(32), default="system")
    message: Mapped[str] = mapped_column(Text, default="")
    # ok | pending | warn | error | info
    level: Mapped[str] = mapped_column(String(16), default="ok")
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
