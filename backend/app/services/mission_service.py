"""Mission lifecycle and serialization.

Mission is the core domain object: objective + agent + context + state + actions
+ events + risk + outcome. Everything the UI renders is derived from these rows.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Action, Approval, Mission, MissionEvent, utcnow
from app.services.event_service import (
    publish_mission,
    publish_outcomes_changed,
    serialize_event,
)

TERMINAL_STATUSES = {"completed", "failed", "human_takeover"}


def next_mission_id(session: Session, base: str) -> str:
    """`TX-1004`, then `TX-1004-2` if that mission already exists."""
    if session.get(Mission, base) is None:
        return base
    suffix = 2
    while session.get(Mission, f"{base}-{suffix}") is not None:
        suffix += 1
    return f"{base}-{suffix}"


def next_sequence_id(session: Session, model, prefix: str, width: int = 3) -> str:
    count = session.query(model).count() + 1
    candidate = f"{prefix}-{count:0{width}d}"
    while session.get(model, candidate) is not None:
        count += 1
        candidate = f"{prefix}-{count:0{width}d}"
    return candidate


def create_mission(
    session: Session,
    *,
    mission_id: str,
    agent: str,
    objective: str,
    inputs: dict[str, Any] | None = None,
) -> Mission:
    mission = Mission(
        id=mission_id,
        agent=agent,
        objective=objective,
        status="created",
        stage="MISSION_CREATED",
        progress=0,
        inputs=inputs or {},
        context={},
        summary={},
    )
    session.add(mission)
    session.commit()
    session.refresh(mission)
    return mission


def update_mission(session: Session, mission: Mission, **fields: Any) -> Mission:
    for key, value in fields.items():
        setattr(mission, key, value)
    mission.updated_at = utcnow()
    if mission.status in TERMINAL_STATUSES and mission.completed_at is None:
        mission.completed_at = utcnow()
    session.add(mission)
    session.commit()
    session.refresh(mission)

    publish_mission(serialize_mission(session, mission))
    if mission.status in TERMINAL_STATUSES:
        publish_outcomes_changed()
    return mission


def pending_approval_for(session: Session, mission_id: str) -> Approval | None:
    return session.scalars(
        select(Approval)
        .where(Approval.mission_id == mission_id)
        .where(Approval.status == "pending")
        .order_by(Approval.created_at.desc())
    ).first()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def serialize_action(action: Action) -> dict[str, Any]:
    return {
        "id": action.id,
        "mission_id": action.mission_id,
        "action_type": action.action_type,
        "description": action.description,
        "risk_level": action.risk_level,
        "requires_approval": action.requires_approval,
        "approval_id": action.approval_id,
        "status": action.status,
        "payload": action.payload or {},
        "result": action.result,
        "executed_via": action.executed_via,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "completed_at": action.completed_at.isoformat() if action.completed_at else None,
    }


def serialize_approval(approval: Approval) -> dict[str, Any]:
    return {
        "id": approval.id,
        "mission_id": approval.mission_id,
        "action_id": approval.action_id,
        "agent": approval.agent,
        "title": approval.title,
        "subject": approval.subject,
        "reason": approval.reason,
        "policy_rule": approval.policy_rule,
        "policy_detail": approval.policy_detail,
        "risk_level": approval.risk_level,
        "evidence": approval.evidence or [],
        "triggered_rules": approval.triggered_rules or [],
        "ai_recommendation": approval.ai_recommendation,
        "impact": approval.impact,
        "status": approval.status,
        "reviewed_by": approval.reviewed_by,
        "reviewed_at": approval.reviewed_at.isoformat() if approval.reviewed_at else None,
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
    }


def serialize_mission(
    session: Session, mission: Mission, *, include_events: bool = False
) -> dict[str, Any]:
    actions = list(
        session.scalars(
            select(Action)
            .where(Action.mission_id == mission.id)
            .order_by(Action.created_at)
        )
    )
    pending = pending_approval_for(session, mission.id)

    payload: dict[str, Any] = {
        "id": mission.id,
        "agent": mission.agent,
        "objective": mission.objective,
        "status": mission.status,
        "stage": mission.stage,
        "progress": mission.progress,
        "result": mission.result,
        "result_label": mission.result_label,
        "inputs": mission.inputs or {},
        "context": mission.context or {},
        "decision": mission.decision,
        "summary": mission.summary or {},
        "error": mission.error,
        "human_involved": mission.human_involved,
        "created_at": mission.created_at.isoformat() if mission.created_at else None,
        "updated_at": mission.updated_at.isoformat() if mission.updated_at else None,
        "completed_at": mission.completed_at.isoformat() if mission.completed_at else None,
        "actions": [serialize_action(a) for a in actions],
        "pending_approval_id": pending.id if pending else None,
    }

    if include_events:
        events = list(
            session.scalars(
                select(MissionEvent)
                .where(MissionEvent.mission_id == mission.id)
                .order_by(MissionEvent.id)
            )
        )
        payload["events"] = [serialize_event(e) for e in events]
    return payload


def serialize_mission_summary(mission: Mission) -> dict[str, Any]:
    return {
        "id": mission.id,
        "agent": mission.agent,
        "objective": mission.objective,
        "status": mission.status,
        "stage": mission.stage,
        "progress": mission.progress,
        "result": mission.result,
        "result_label": mission.result_label,
        "human_involved": mission.human_involved,
        "created_at": mission.created_at.isoformat() if mission.created_at else None,
        "completed_at": mission.completed_at.isoformat() if mission.completed_at else None,
    }


def list_missions(session: Session, agent: str | None = None) -> list[Mission]:
    stmt = select(Mission).order_by(Mission.created_at.desc())
    if agent:
        stmt = stmt.where(Mission.agent == agent)
    return list(session.scalars(stmt))
