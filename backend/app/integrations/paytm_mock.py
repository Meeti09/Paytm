"""Paytm integration boundary.

`PaytmAdapter` is the interface the agents code against. `MockPaytmAdapter` is
the only implementation shipped with this prototype: it reads and writes the
local demo database.

This prototype has no access to Paytm production systems. Every customer,
merchant, transaction and policy here is fictional demo data. A future
`ProductionPaytmAdapter` would implement the same interface against real APIs;
no agent code would change.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import (
    Customer,
    Lead,
    Merchant,
    SupportCase,
    Transaction,
    utcnow,
)

log = logging.getLogger("pulse.paytm")

# Demo policy documents the Resolve teammate can retrieve.
DEMO_POLICIES: dict[str, dict[str, Any]] = {
    "POL-REFUND-01": {
        "id": "POL-REFUND-01",
        "title": "Debited but not settled to merchant",
        "summary": (
            "Where a customer debit is confirmed and merchant settlement has "
            "failed or is stuck, the debited amount is refundable to source."
        ),
        "conditions": [
            "Customer debit confirmed on the transaction record",
            "Merchant settlement status is failed or pending",
            "Transaction is within the 7-day refund window",
        ],
        "autonomy": "Refunds are autonomous at or below the configured threshold.",
    },
    "POL-DELAY-01": {
        "id": "POL-DELAY-01",
        "title": "Delayed settlement enquiry",
        "summary": "Settlement delays are resolved by re-triggering settlement or refunding to source.",
        "conditions": ["Transaction is in a non-final state"],
        "autonomy": "Status checks and notifications are always autonomous.",
    },
    "POL-ESCALATION-01": {
        "id": "POL-ESCALATION-01",
        "title": "Repeat complaint handling",
        "summary": (
            "Where a customer has previously reported the same issue, the next "
            "customer-facing action is reviewed by a human before it is sent."
        ),
        "conditions": ["One or more prior unresolved cases for the same customer"],
        "autonomy": "Customer-facing action requires human review.",
    },
}

REFUND_WINDOW_DAYS = 7


def as_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; normalise before any arithmetic."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PaytmAdapter(ABC):
    """Interface between Paytm Pulse and Paytm systems."""

    name: str = "paytm"

    @abstractmethod
    def get_customer(self, session: Session, customer_id: str) -> dict | None: ...

    @abstractmethod
    def get_transaction(self, session: Session, transaction_id: str) -> dict | None: ...

    @abstractmethod
    def get_merchant(self, session: Session, merchant_id: str) -> dict | None: ...

    @abstractmethod
    def get_customer_history(self, session: Session, customer_id: str) -> dict: ...

    @abstractmethod
    def get_policy(self, session: Session, policy_id: str) -> dict | None: ...

    @abstractmethod
    def execute_refund(
        self, session: Session, transaction_id: str, amount: float, reference: str
    ) -> dict: ...

    @abstractmethod
    def verify_refund(self, session: Session, transaction_id: str) -> dict: ...

    @abstractmethod
    def send_notification(
        self, session: Session, customer_id: str, channel: str, message: str
    ) -> dict: ...


class MockPaytmAdapter(PaytmAdapter):
    """Demo implementation backed by the local seeded database.

    State changes are real within this prototype: a refund actually mutates the
    transaction row, and `verify_refund` re-reads that row rather than returning
    a canned success.
    """

    name = "mock_paytm"

    # ---- reads ---------------------------------------------------------

    def get_customer(self, session: Session, customer_id: str) -> dict | None:
        row = session.get(Customer, customer_id)
        if not row:
            return None
        return {
            "id": row.id,
            "name": row.name,
            "phone": row.phone,
            "language": row.language,
            "segment": row.segment,
            "joined_on": row.joined_on,
        }

    def get_transaction(self, session: Session, transaction_id: str) -> dict | None:
        row = session.get(Transaction, transaction_id)
        return self._transaction_dict(row) if row else None

    def find_disputed_transaction(
        self, session: Session, customer_id: str, amount: float | None = None
    ) -> dict | None:
        """Locate the transaction a customer is most likely complaining about."""
        stmt = (
            select(Transaction)
            .where(Transaction.customer_id == customer_id)
            .where(Transaction.status.in_(["debited_not_settled", "pending", "failed"]))
            .order_by(Transaction.timestamp.desc())
        )
        rows = list(session.scalars(stmt))
        if amount is not None:
            for row in rows:
                if abs(row.amount - amount) < 0.01:
                    return self._transaction_dict(row)
        return self._transaction_dict(rows[0]) if rows else None

    def get_merchant(self, session: Session, merchant_id: str) -> dict | None:
        row = session.get(Merchant, merchant_id)
        return self._merchant_dict(row) if row else None

    def get_customer_history(self, session: Session, customer_id: str) -> dict:
        txns = list(
            session.scalars(
                select(Transaction)
                .where(Transaction.customer_id == customer_id)
                .order_by(Transaction.timestamp.desc())
            )
        )
        cases = list(
            session.scalars(
                select(SupportCase)
                .where(SupportCase.customer_id == customer_id)
                .order_by(SupportCase.created_at.desc())
            )
        )
        prior_unresolved = [c for c in cases if c.status in ("open", "reopened")]
        return {
            "transaction_count": len(txns),
            "transactions": [self._transaction_dict(t) for t in txns[:6]],
            "case_count": len(cases),
            "cases": [
                {
                    "id": c.id,
                    "issue": c.issue,
                    "status": c.status,
                    "sentiment": c.sentiment,
                    "transaction_id": c.transaction_id,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in cases[:6]
            ],
            "prior_unresolved_cases": len(prior_unresolved),
            "lifetime_value": round(
                sum(t.amount for t in txns if t.status == "success"), 2
            ),
        }

    def get_policy(self, session: Session, policy_id: str) -> dict | None:
        return DEMO_POLICIES.get(policy_id)

    def get_settlement_status(self, session: Session, transaction_id: str) -> dict:
        row = session.get(Transaction, transaction_id)
        if not row:
            return {"found": False}
        return {
            "found": True,
            "transaction_id": row.id,
            "settlement_status": row.settlement_status,
            "merchant_credited": row.settlement_status == "settled",
            "customer_debited": row.status
            in ("success", "debited_not_settled", "refunded"),
        }

    def is_refund_eligible(self, session: Session, transaction_id: str) -> dict:
        """Deterministic eligibility check against POL-REFUND-01."""
        row = session.get(Transaction, transaction_id)
        if not row:
            return {"eligible": False, "reason": "Transaction not found"}
        if row.status == "refunded":
            return {"eligible": False, "reason": "Transaction already refunded"}
        debited = row.status in ("success", "debited_not_settled")
        settled = row.settlement_status == "settled"
        age = utcnow() - as_utc(row.timestamp)
        in_window = age <= timedelta(days=REFUND_WINDOW_DAYS)
        eligible = debited and not settled and in_window
        return {
            "eligible": eligible,
            "customer_debited": debited,
            "merchant_settled": settled,
            "within_window": in_window,
            "window_days": REFUND_WINDOW_DAYS,
            "reason": (
                "Customer debit confirmed, merchant settlement not completed, "
                f"within the {REFUND_WINDOW_DAYS}-day refund window."
                if eligible
                else "Transaction does not meet POL-REFUND-01 conditions."
            ),
        }

    # ---- writes --------------------------------------------------------

    def execute_refund(
        self, session: Session, transaction_id: str, amount: float, reference: str
    ) -> dict:
        row = session.get(Transaction, transaction_id)
        if not row:
            return {"success": False, "error": "TRANSACTION_NOT_FOUND"}
        if row.status == "refunded":
            return {
                "success": False,
                "error": "ALREADY_REFUNDED",
                "transaction_id": transaction_id,
            }
        if abs(amount - row.amount) > 0.01:
            # Never move an amount that does not match the ledger.
            return {
                "success": False,
                "error": "AMOUNT_MISMATCH",
                "ledger_amount": row.amount,
                "requested_amount": amount,
            }

        row.status = "refunded"
        row.settlement_status = "refunded_to_source"
        session.add(row)
        session.commit()

        return {
            "success": True,
            "transaction_id": transaction_id,
            "amount": row.amount,
            "refund_reference": reference,
            "credited_to": "source account",
            "expected_settlement": "instant (simulated)",
        }

    def verify_refund(self, session: Session, transaction_id: str) -> dict:
        """Re-read the record. This is a real read-back, not a canned response."""
        session.expire_all()
        row = session.get(Transaction, transaction_id)
        if not row:
            return {"verified": False, "reason": "Transaction not found"}
        verified = row.status == "refunded"
        return {
            "verified": verified,
            "transaction_id": row.id,
            "status": row.status,
            "settlement_status": row.settlement_status,
            "amount": row.amount,
            "reason": (
                "Transaction ledger state confirms refund to source."
                if verified
                else f"Transaction is still in state '{row.status}'."
            ),
        }

    def send_notification(
        self, session: Session, customer_id: str, channel: str, message: str
    ) -> dict:
        customer = session.get(Customer, customer_id)
        if not customer:
            return {"success": False, "error": "CUSTOMER_NOT_FOUND"}
        # Simulated delivery. No message leaves this machine.
        return {
            "success": True,
            "channel": channel,
            "to": customer.phone,
            "language": customer.language,
            "message": message,
            "delivery": "simulated",
        }

    def create_case(
        self,
        session: Session,
        customer_id: str,
        transaction_id: str | None,
        issue: str,
        sentiment: str,
        mission_id: str,
        status: str = "open",
        assigned_agent: str = "resolve",
    ) -> dict:
        case_id = self._next_id(session, SupportCase, "CASE")
        case = SupportCase(
            id=case_id,
            customer_id=customer_id,
            transaction_id=transaction_id,
            issue=issue,
            sentiment=sentiment,
            status=status,
            assigned_agent=assigned_agent,
            mission_id=mission_id,
        )
        session.add(case)
        session.commit()
        return {"success": True, "case_id": case_id, "status": status}

    def close_case(self, session: Session, case_id: str, resolution: str) -> dict:
        case = session.get(SupportCase, case_id)
        if not case:
            return {"success": False, "error": "CASE_NOT_FOUND"}
        case.status = "resolved"
        case.resolution = resolution
        session.add(case)
        session.commit()
        return {"success": True, "case_id": case_id, "status": "resolved"}

    def reassign_case(self, session: Session, case_id: str, assignee: str) -> dict:
        case = session.get(SupportCase, case_id)
        if not case:
            return {"success": False, "error": "CASE_NOT_FOUND"}
        case.status = "with_specialist"
        case.assigned_agent = assignee
        session.add(case)
        session.commit()
        return {"success": True, "case_id": case_id, "assigned_agent": assignee}

    # ---- merchant / lead side -------------------------------------------

    def search_merchants(
        self,
        session: Session,
        location: str = "",
        category: str = "",
    ) -> list[dict]:
        stmt = select(Merchant)
        rows = list(session.scalars(stmt))
        if location:
            needle = location.strip().lower()
            rows = [m for m in rows if needle in m.location.lower()]
        if category:
            needle = category.strip().lower()
            rows = [m for m in rows if needle == m.category.lower()]
        return [self._merchant_dict(m) for m in rows]

    def get_paytm_status(self, session: Session, merchant_id: str) -> dict:
        row = session.get(Merchant, merchant_id)
        if not row:
            return {"found": False}
        return {
            "found": True,
            "merchant_id": row.id,
            "paytm_status": row.paytm_status,
            "onboarded": row.paytm_status == "active",
            "source": "demo dataset",
        }

    def book_meeting(
        self, session: Session, lead_id: str, slot: str, attendee: str
    ) -> dict:
        lead = session.get(Lead, lead_id)
        if not lead:
            return {"success": False, "error": "LEAD_NOT_FOUND"}
        lead.meeting_slot = slot
        lead.updated_at = utcnow()
        session.add(lead)
        session.commit()
        return {
            "success": True,
            "lead_id": lead_id,
            "slot": slot,
            "attendee": attendee,
            "calendar": "simulated",
        }

    def submit_onboarding(self, session: Session, merchant_id: str) -> dict:
        row = session.get(Merchant, merchant_id)
        if not row:
            return {"success": False, "error": "MERCHANT_NOT_FOUND"}
        return {
            "success": True,
            "merchant_id": merchant_id,
            "stage": "onboarding_initiated",
            "note": "Simulated onboarding hand-off",
        }

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _transaction_dict(row: Transaction) -> dict:
        return {
            "id": row.id,
            "customer_id": row.customer_id,
            "merchant_id": row.merchant_id,
            "amount": row.amount,
            "payment_method": row.payment_method,
            "status": row.status,
            "settlement_status": row.settlement_status,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        }

    @staticmethod
    def _merchant_dict(row: Merchant) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "category": row.category,
            "location": row.location,
            "paytm_status": row.paytm_status,
            "estimated_volume": row.estimated_volume,
            "contact": row.contact,
            "website": row.website,
            "notes": row.notes,
        }

    @staticmethod
    def _next_id(session: Session, model, prefix: str) -> str:
        count = session.query(model).count()
        return f"{prefix}-{count + 1:03d}"


paytm: PaytmAdapter = MockPaytmAdapter()
