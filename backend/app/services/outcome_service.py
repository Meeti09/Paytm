"""Outcome aggregation.

Every number on the Outcomes screen is computed here from mission, approval,
action and lead records created by actual runs. Nothing is hardcoded, and each
metric carries a `basis` string naming the records it was counted from — so any
figure on screen can be traced back to the database.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Action, Approval, Lead, Mission, MissionEvent

TERMINAL = ("completed", "failed", "human_takeover")

# Lead stage ordering, mirrored from the Grow agent.
STAGE_RANK = {
    "qualified": 3,
    "contacted": 4,
    "responded": 5,
    "sales_ready": 6,
    "meeting_booked": 7,
}

RESULT_LABELS = {
    "resolved_autonomously": "Resolved autonomously",
    "resolved_with_approval": "Resolved after human approval",
    "rejected_by_human": "Rejected — handed to a specialist",
    "handled_by_human": "Handled by a human",
    "meeting_booked": "Meeting booked",
    "no_qualified_leads": "No sales-ready merchant",
    "failed": "Failed",
}


def _metric(value: Any, label: str, basis: str) -> dict[str, Any]:
    return {"value": value, "label": label, "basis": basis}


def resolve_outcomes(session: Session) -> dict[str, Any]:
    missions = list(
        session.scalars(select(Mission).where(Mission.agent == "resolve"))
    )
    terminal = [m for m in missions if m.status in TERMINAL]

    escalated_ids = set(
        session.scalars(
            select(Approval.mission_id).join(
                Mission, Mission.id == Approval.mission_id
            ).where(Mission.agent == "resolve")
        )
    )
    approvals_granted = session.scalar(
        select(func.count(Approval.id))
        .join(Mission, Mission.id == Approval.mission_id)
        .where(Mission.agent == "resolve")
        .where(Approval.status == "approved")
    ) or 0
    approvals_rejected = session.scalar(
        select(func.count(Approval.id))
        .join(Mission, Mission.id == Approval.mission_id)
        .where(Mission.agent == "resolve")
        .where(Approval.status == "rejected")
    ) or 0

    processed = len(terminal)
    autonomous = sum(1 for m in terminal if m.result == "resolved_autonomously")
    escalated = sum(1 for m in missions if m.id in escalated_ids)
    failed = sum(1 for m in missions if m.status == "failed")

    autonomy_rate = round(autonomous / processed * 100) if processed else None

    return {
        "metrics": [
            _metric(processed, "Processed", "Resolve missions in a terminal state"),
            _metric(
                autonomous,
                "Resolved autonomously",
                "Missions with result resolved_autonomously",
            ),
            _metric(escalated, "Escalated", "Missions that created an approval request"),
            _metric(approvals_granted, "Human approvals", "Approval records marked approved"),
            _metric(failed, "Failed", "Missions in a failed state"),
        ],
        "autonomy_rate": autonomy_rate,
        "autonomy_rate_basis": (
            f"{autonomous} autonomous of {processed} processed"
            if processed
            else "No processed missions yet"
        ),
        "approvals_rejected": approvals_rejected,
        "in_flight": sum(1 for m in missions if m.status not in TERMINAL),
    }


def grow_outcomes(session: Session) -> dict[str, Any]:
    leads = list(session.scalars(select(Lead)))
    missions = list(session.scalars(select(Mission).where(Mission.agent == "grow")))

    def at_least(stage: str) -> int:
        floor = STAGE_RANK[stage]
        return sum(1 for lead in leads if lead.stage_rank >= floor)

    return {
        "metrics": [
            _metric(len(leads), "Merchants evaluated", "Lead records scored by Grow"),
            _metric(at_least("qualified"), "Qualified", "Leads at stage qualified or beyond"),
            _metric(at_least("contacted"), "Contacted", "Leads that received outreach"),
            _metric(at_least("sales_ready"), "Sales-ready", "Leads qualified from a reply"),
            _metric(
                at_least("meeting_booked"),
                "Meetings booked",
                "Leads with a booked meeting",
            ),
        ],
        "missions": len(missions),
        "in_flight": sum(1 for m in missions if m.status not in TERMINAL),
    }


def mission_table(session: Session) -> list[dict[str, Any]]:
    missions = list(
        session.scalars(select(Mission).order_by(Mission.created_at.desc()))
    )
    approval_counts: dict[str, int] = {}
    for mission_id, count in session.execute(
        select(Approval.mission_id, func.count(Approval.id)).group_by(Approval.mission_id)
    ):
        approval_counts[mission_id] = count

    rows = []
    for mission in missions:
        rows.append(
            {
                "id": mission.id,
                "agent": mission.agent,
                "objective": mission.objective,
                "status": mission.status,
                "result": mission.result,
                "result_label": mission.result_label
                or RESULT_LABELS.get(mission.result or "", "In progress"),
                "human_involved": bool(
                    mission.human_involved or approval_counts.get(mission.id)
                ),
                "approvals": approval_counts.get(mission.id, 0),
                "created_at": mission.created_at.isoformat() if mission.created_at else None,
                "completed_at": mission.completed_at.isoformat()
                if mission.completed_at
                else None,
            }
        )
    return rows


def build_outcomes(session: Session) -> dict[str, Any]:
    events = session.scalar(select(func.count(MissionEvent.id))) or 0
    actions_executed = (
        session.scalar(
            select(func.count(Action.id)).where(Action.status.in_(["executed", "verified"]))
        )
        or 0
    )
    missions_total = session.scalar(select(func.count(Mission.id))) or 0

    return {
        "resolve": resolve_outcomes(session),
        "grow": grow_outcomes(session),
        "missions": mission_table(session),
        "trace": {
            "missions_recorded": missions_total,
            "events_recorded": events,
            "actions_executed": actions_executed,
        },
        "note": (
            "Every figure is computed from mission, approval, action and lead "
            "records created by runs in this session. Reset clears them all."
        ),
    }
