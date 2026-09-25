"""Demo control API — repeatable runs for a live presentation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents import orchestrator
from app.agents.permissions import permissions_summary
from app.config import integration_status
from app.db import get_db
from app.demo.scenarios import GROW_SCENARIO, RESOLVE_SCENARIOS, resolve_scenario
from app.demo.seed import reset_demo
from app.models.models import Customer, Merchant, Mission, Transaction
from app.policy.risk import current_policy
from app.services.event_service import (
    publish_approvals_changed,
    publish_outcomes_changed,
    bus,
)
from app.services.mission_service import create_mission, next_mission_id, serialize_mission

router = APIRouter(prefix="/api/demo", tags=["demo"])


class ResolveDemoIn(BaseModel):
    scenario: str | None = None
    customer_id: str | None = None
    message: str | None = None


class GrowDemoIn(BaseModel):
    location: str = GROW_SCENARIO["location"]
    target_count: int = GROW_SCENARIO["target_count"]
    category: str = ""


@router.get("/scenarios")
def scenarios(db: Session = Depends(get_db)):
    return {
        "resolve": RESOLVE_SCENARIOS,
        "grow": GROW_SCENARIO,
        "customers": [
            {"id": c.id, "name": c.name, "language": c.language}
            for c in db.query(Customer).order_by(Customer.id).all()
        ],
        "dataset": {
            "customers": db.query(Customer).count(),
            "merchants": db.query(Merchant).count(),
            "transactions": db.query(Transaction).count(),
        },
    }


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return {
        "integrations": integration_status(),
        "policy": current_policy(),
        "permissions": permissions_summary(),
        "missions": db.query(Mission).count(),
        "live_clients": bus.subscriber_count,
        "disclosure": (
            "Prototype. Simulated Paytm integration boundary — no production "
            "Paytm access. All customer, merchant and transaction records are "
            "fictional demo data."
        ),
    }


@router.post("/reset")
def reset(db: Session = Depends(get_db)):
    orchestrator.cancel_all()
    cleared = reset_demo(db)
    bus.publish("demo_reset", {"cleared": cleared})
    publish_approvals_changed()
    publish_outcomes_changed()
    return {
        "reset": True,
        "cleared": cleared,
        "seeded": {
            "customers": db.query(Customer).count(),
            "merchants": db.query(Merchant).count(),
            "transactions": db.query(Transaction).count(),
        },
    }


@router.post("/resolve", status_code=201)
def run_resolve(body: ResolveDemoIn, db: Session = Depends(get_db)):
    customer_id = body.customer_id
    message = body.message

    if body.scenario:
        scenario = resolve_scenario(body.scenario)
        if scenario is None:
            raise HTTPException(status_code=404, detail="Unknown scenario")
        customer_id = scenario["customer_id"]
        message = scenario["message"]

    if not customer_id or not message:
        raise HTTPException(
            status_code=400, detail="A scenario, or a customer_id and message, is required"
        )
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found in the demo dataset")

    mission_id = next_mission_id(db, _next_ref(db, "resolve"))
    mission = create_mission(
        db,
        mission_id=mission_id,
        agent="resolve",
        objective="Resolve customer payment issue",
        inputs={
            "customer_id": customer_id,
            "message": message,
            "scenario": body.scenario,
        },
    )
    orchestrator.start_mission(mission.id)
    return serialize_mission(db, mission)


@router.post("/grow", status_code=201)
def run_grow(body: GrowDemoIn, db: Session = Depends(get_db)):
    if body.target_count < 1 or body.target_count > 20:
        raise HTTPException(status_code=400, detail="target_count must be between 1 and 20")

    mission_id = next_mission_id(db, _next_ref(db, "grow"))
    objective = (
        f"Find {body.target_count} high-potential merchants in {body.location}"
        if body.location
        else f"Find {body.target_count} high-potential merchants"
    )
    mission = create_mission(
        db,
        mission_id=mission_id,
        agent="grow",
        objective=objective,
        inputs={
            "location": body.location,
            "target_count": body.target_count,
            "category": body.category,
        },
    )
    orchestrator.start_mission(mission.id)
    return serialize_mission(db, mission)


def _next_ref(db: Session, agent: str) -> str:
    prefix = "R" if agent == "resolve" else "G"
    count = db.query(Mission).filter(Mission.agent == agent).count() + 1
    return f"{prefix}-{count:04d}"
