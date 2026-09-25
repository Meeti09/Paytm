"""Approval Queue API — the governance surface.

Approval state is validated server-side on every transition. A browser can ask
for an approval to be granted; it can never execute the underlying action, and
it can never re-decide an approval that has already been reviewed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import orchestrator
from app.db import get_db
from app.models.models import Action, Approval, Mission, utcnow
from app.policy.risk import current_policy
from app.services.event_service import (
    publish_approvals_changed,
    publish_mission,
    record_event,
)
from app.services.mission_service import serialize_approval, serialize_mission

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class Review(BaseModel):
    reviewer: str = "Operator"
    note: str = ""


def _enriched(db: Session, approval: Approval) -> dict:
    payload = serialize_approval(approval)
    mission = db.get(Mission, approval.mission_id)
    action = db.get(Action, approval.action_id)
    payload["mission"] = (
        {
            "id": mission.id,
            "agent": mission.agent,
            "objective": mission.objective,
            "status": mission.status,
            "context": mission.context or {},
            "decision": mission.decision,
        }
        if mission
        else None
    )
    payload["action"] = (
        {
            "id": action.id,
            "action_type": action.action_type,
            "description": action.description,
            "status": action.status,
            "payload": action.payload or {},
        }
        if action
        else None
    )
    return payload


@router.get("")
def list_approvals(status: str | None = "pending", db: Session = Depends(get_db)):
    stmt = select(Approval).order_by(Approval.created_at.desc())
    if status and status != "all":
        stmt = stmt.where(Approval.status == status)
    approvals = list(db.scalars(stmt))
    return {
        "approvals": [_enriched(db, a) for a in approvals],
        "policy": current_policy(),
        "pending_count": db.query(Approval).filter(Approval.status == "pending").count(),
    }


@router.get("/{approval_id}")
def get_approval(approval_id: str, db: Session = Depends(get_db)):
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return _enriched(db, approval)


def _load_pending(db: Session, approval_id: str) -> Approval:
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Approval has already been {approval.status}",
        )
    mission = db.get(Mission, approval.mission_id)
    if mission is None:
        raise HTTPException(status_code=409, detail="Mission no longer exists")
    if mission.status not in ("waiting_approval", "running", "paused"):
        raise HTTPException(
            status_code=409,
            detail=f"Mission is {mission.status}; approval can no longer be applied",
        )
    action = db.get(Action, approval.action_id)
    if action is None or action.mission_id != approval.mission_id:
        raise HTTPException(status_code=409, detail="Approval does not match its action")
    return approval


@router.post("/{approval_id}/approve")
def approve(approval_id: str, body: Review, db: Session = Depends(get_db)):
    approval = _load_pending(db, approval_id)

    approval.status = "approved"
    approval.reviewed_by = body.reviewer
    approval.reviewed_at = utcnow()
    db.add(approval)
    db.commit()

    record_event(
        db,
        approval.mission_id,
        "APPROVAL_GRANTED",
        f"{body.reviewer} approved: {approval.title}",
        actor="human",
        level="ok",
        meta={"approval_id": approval.id, "policy_rule": approval.policy_rule},
    )
    publish_approvals_changed()
    orchestrator.resume_after_approval(approval.mission_id, approval.id, body.reviewer)
    return _enriched(db, approval)


@router.post("/{approval_id}/reject")
def reject(approval_id: str, body: Review, db: Session = Depends(get_db)):
    approval = _load_pending(db, approval_id)

    approval.status = "rejected"
    approval.reviewed_by = body.reviewer
    approval.reviewed_at = utcnow()
    db.add(approval)

    action = db.get(Action, approval.action_id)
    if action is not None:
        action.status = "cancelled"
        action.completed_at = utcnow()
        db.add(action)
    db.commit()

    reason = f"{body.reviewer} rejected: {approval.title}"
    if body.note.strip():
        reason += f" — {body.note.strip()}"
    record_event(
        db,
        approval.mission_id,
        "APPROVAL_REJECTED",
        reason,
        actor="human",
        level="warn",
        meta={"approval_id": approval.id, "note": body.note},
    )
    publish_approvals_changed()
    orchestrator.resume_after_rejection(approval.mission_id, approval.id, body.reviewer)
    return _enriched(db, approval)


@router.post("/{approval_id}/takeover")
def takeover(approval_id: str, body: Review, db: Session = Depends(get_db)):
    approval = _load_pending(db, approval_id)

    approval.status = "taken_over"
    approval.reviewed_by = body.reviewer
    approval.reviewed_at = utcnow()
    db.add(approval)

    action = db.get(Action, approval.action_id)
    if action is not None:
        action.status = "cancelled"
        action.completed_at = utcnow()
        db.add(action)
    db.commit()

    orchestrator.takeover(approval.mission_id, body.reviewer)
    publish_approvals_changed()

    db.expire_all()
    mission = db.get(Mission, approval.mission_id)
    if mission:
        publish_mission(serialize_mission(db, mission))
    return _enriched(db, approval)
