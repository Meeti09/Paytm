"""Simulated Paytm boundary (Architecture.md §21).

These endpoints exist so the execution layer — n8n — can act against a real HTTP
surface instead of reaching into the application internals. They are simulated:
no production Paytm system is involved and every record is fictional demo data.

Reads are open. Every mutation requires the internal service key, so a browser
can never move money or send a notification directly — only the execution layer
can, and only after the policy engine has cleared the action.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.integrations.paytm_mock import DEMO_POLICIES, MockPaytmAdapter
from app.models.models import Lead, Merchant, utcnow

router = APIRouter(prefix="/paytm", tags=["paytm (simulated)"])
paytm = MockPaytmAdapter()


def require_internal_key(x_pulse_internal_key: str | None = Header(default=None)) -> None:
    if x_pulse_internal_key != settings.internal_api_key:
        raise HTTPException(
            status_code=401,
            detail="Mutating the payments boundary requires the internal service key.",
        )


class RefundIn(BaseModel):
    transaction_id: str
    amount: float
    reference: str = "PULSE"


class NotificationIn(BaseModel):
    customer_id: str
    channel: str = "sms"
    message: str


class OnboardingIn(BaseModel):
    merchant_id: str


class MeetingIn(BaseModel):
    lead_id: str
    slot: str
    attendee: str = ""


class OutreachIn(BaseModel):
    message: str
    channel: str = "simulated"


# ---- reads ---------------------------------------------------------------


@router.get("/customer/{customer_id}")
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    record = paytm.get_customer(db, customer_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return record


@router.get("/transaction/{transaction_id}")
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    record = paytm.get_transaction(db, transaction_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return record


@router.get("/transaction/{transaction_id}/settlement")
def get_settlement(transaction_id: str, db: Session = Depends(get_db)):
    record = paytm.get_settlement_status(db, transaction_id)
    if not record.get("found"):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return record


@router.get("/transaction/{transaction_id}/refund-eligibility")
def get_eligibility(transaction_id: str, db: Session = Depends(get_db)):
    return paytm.is_refund_eligible(db, transaction_id)


@router.get("/merchant/{merchant_id}")
def get_merchant(merchant_id: str, db: Session = Depends(get_db)):
    record = paytm.get_merchant(db, merchant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return record


@router.get("/customer/{customer_id}/disputed-transaction")
def get_disputed(
    customer_id: str, amount: float | None = None, db: Session = Depends(get_db)
):
    """The transaction a customer is most likely disputing.

    Used by the investigation workflow when the inbound message does not name a
    transaction reference.
    """
    record = paytm.find_disputed_transaction(db, customer_id, amount)
    if record is None:
        raise HTTPException(status_code=404, detail="No disputed transaction found")
    return record


@router.get("/customer/{customer_id}/history")
def get_history(customer_id: str, db: Session = Depends(get_db)):
    if paytm.get_customer(db, customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return paytm.get_customer_history(db, customer_id)


@router.get("/policy/{policy_id}")
def get_policy(policy_id: str):
    policy = DEMO_POLICIES.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.get("/merchants")
def search_merchants(location: str = "", category: str = "", db: Session = Depends(get_db)):
    return {"merchants": paytm.search_merchants(db, location=location, category=category)}


@router.get("/leads")
def list_leads(mission_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Lead).order_by(Lead.score.desc())
    if mission_id:
        stmt = stmt.where(Lead.mission_id == mission_id)
    leads = list(db.scalars(stmt))
    merchants = {m.id: m for m in db.scalars(select(Merchant))}
    return {
        "leads": [
            {
                "id": lead.id,
                "mission_id": lead.mission_id,
                "merchant_id": lead.merchant_id,
                "merchant": getattr(merchants.get(lead.merchant_id), "name", ""),
                "score": lead.score,
                "stage": lead.stage,
                "reason": lead.reason,
                "next_action": lead.next_action,
                "meeting_slot": lead.meeting_slot,
            }
            for lead in leads
        ]
    }


# ---- mutations (internal service key required) ---------------------------


@router.post("/refund", dependencies=[Depends(require_internal_key)])
def post_refund(body: RefundIn, db: Session = Depends(get_db)):
    result = paytm.execute_refund(db, body.transaction_id, body.amount, body.reference)
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post("/refund/verify", dependencies=[Depends(require_internal_key)])
def post_verify(body: RefundIn, db: Session = Depends(get_db)):
    return paytm.verify_refund(db, body.transaction_id)


@router.post("/notification", dependencies=[Depends(require_internal_key)])
def post_notification(body: NotificationIn, db: Session = Depends(get_db)):
    result = paytm.send_notification(db, body.customer_id, body.channel, body.message)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result)
    return result


@router.post("/leads/{lead_id}/outreach", dependencies=[Depends(require_internal_key)])
def post_outreach(lead_id: str, body: OutreachIn, db: Session = Depends(get_db)):
    """Record that outreach was sent on the simulated channel."""
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.outreach_message = body.message
    lead.outreach_channel = body.channel
    lead.stage = "contacted"
    lead.stage_rank = 4
    lead.next_action = "Await merchant response"
    lead.updated_at = utcnow()
    db.add(lead)
    db.commit()
    return {
        "success": True,
        "lead_id": lead_id,
        "stage": lead.stage,
        "delivery": "simulated",
    }


@router.post("/meeting", dependencies=[Depends(require_internal_key)])
def post_meeting(body: MeetingIn, db: Session = Depends(get_db)):
    result = paytm.book_meeting(db, body.lead_id, body.slot, body.attendee)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result)
    return result


@router.post("/onboarding", dependencies=[Depends(require_internal_key)])
def post_onboarding(body: OnboardingIn, db: Session = Depends(get_db)):
    result = paytm.submit_onboarding(db, body.merchant_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result)
    return result
