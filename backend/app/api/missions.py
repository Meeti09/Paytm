"""Mission API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import orchestrator
from app.db import get_db
from app.models.models import Lead, Mission, MissionEvent
from app.services.event_service import serialize_event
from app.services.mission_service import (
    create_mission,
    list_missions,
    next_mission_id,
    serialize_mission,
    serialize_mission_summary,
)

router = APIRouter(prefix="/api/missions", tags=["missions"])


class MissionCreate(BaseModel):
    agent: str = Field(pattern="^(resolve|grow)$")
    objective: str
    inputs: dict = Field(default_factory=dict)
    start: bool = True


class OperatorAction(BaseModel):
    operator: str = "Operator"


class ReplyIn(BaseModel):
    lead_id: str
    text: str


@router.get("")
def get_missions(agent: str | None = None, db: Session = Depends(get_db)):
    missions = list_missions(db, agent)
    return {"missions": [serialize_mission_summary(m) for m in missions]}


@router.post("", status_code=201)
def post_mission(body: MissionCreate, db: Session = Depends(get_db)):
    prefix = "TX" if body.agent == "resolve" else "G"
    base = body.inputs.get("mission_ref") or next_mission_id(
        db, f"{prefix}-{db.query(Mission).count() + 1:04d}"
    )
    mission = create_mission(
        db,
        mission_id=next_mission_id(db, base),
        agent=body.agent,
        objective=body.objective,
        inputs=body.inputs,
    )
    if body.start:
        orchestrator.start_mission(mission.id)
    return serialize_mission(db, mission)


@router.get("/{mission_id}")
def get_mission(mission_id: str, db: Session = Depends(get_db)):
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    payload = serialize_mission(db, mission, include_events=True)
    payload["running"] = orchestrator.is_running(mission_id)
    return payload


@router.get("/{mission_id}/events")
def get_mission_events(mission_id: str, db: Session = Depends(get_db)):
    if db.get(Mission, mission_id) is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    events = list(
        db.scalars(
            select(MissionEvent)
            .where(MissionEvent.mission_id == mission_id)
            .order_by(MissionEvent.id)
        )
    )
    return {"events": [serialize_event(e) for e in events]}


@router.post("/{mission_id}/start")
def start(mission_id: str, db: Session = Depends(get_db)):
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    if orchestrator.is_running(mission_id):
        raise HTTPException(status_code=409, detail="Mission is already running")
    if mission.status in ("completed", "failed", "human_takeover"):
        raise HTTPException(status_code=409, detail="Mission has already finished")
    orchestrator.start_mission(mission_id)
    return serialize_mission(db, mission)


@router.post("/{mission_id}/pause")
def pause(mission_id: str, db: Session = Depends(get_db)):
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    orchestrator.pause(mission_id)
    db.refresh(mission)
    return serialize_mission(db, mission)


@router.post("/{mission_id}/retry")
def retry(mission_id: str, db: Session = Depends(get_db)):
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    if mission.status not in ("paused", "needs_attention", "failed"):
        raise HTTPException(
            status_code=409, detail="Only a paused or failed mission can be retried"
        )
    orchestrator.retry_mission(mission_id)
    return serialize_mission(db, mission)


@router.post("/{mission_id}/takeover")
def takeover(mission_id: str, body: OperatorAction, db: Session = Depends(get_db)):
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    if mission.status in ("completed", "failed", "human_takeover"):
        raise HTTPException(status_code=409, detail="Mission has already finished")
    orchestrator.takeover(mission_id, body.operator)
    db.expire_all()
    mission = db.get(Mission, mission_id)
    return serialize_mission(db, mission)


@router.post("/{mission_id}/reply")
def reply(mission_id: str, body: ReplyIn, db: Session = Depends(get_db)):
    """Feed a simulated merchant reply into a waiting Grow mission."""
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    if mission.agent != "grow":
        raise HTTPException(status_code=400, detail="Replies apply to Grow missions only")
    if mission.status != "waiting_response":
        raise HTTPException(
            status_code=409, detail="Mission is not waiting for a merchant response"
        )
    lead = db.get(Lead, body.lead_id)
    if lead is None or lead.mission_id != mission_id:
        raise HTTPException(status_code=404, detail="Lead not found on this mission")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Reply text is required")

    orchestrator.submit_reply(mission_id, body.lead_id, body.text.strip())
    return serialize_mission(db, mission)
