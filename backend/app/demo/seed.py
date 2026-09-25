"""Seeded demo dataset.

Everything in this file is FICTIONAL. These are not Paytm customers, merchants,
transactions or policies, and the dataset makes no claim about which real
businesses accept Paytm.

The merchant volumes below are chosen so the Grow lead scorer produces exactly
four qualified leads out of twelve Thane prospects. The Outcomes screen reports
that because the scorer computed it — not because it was typed in.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.models import (
    Action,
    Approval,
    Customer,
    Lead,
    Merchant,
    Mission,
    MissionEvent,
    SupportCase,
    Transaction,
    utcnow,
)

# ---------------------------------------------------------------------------
# Customers (demo)
# ---------------------------------------------------------------------------

CUSTOMERS = [
    dict(
        id="CUST-001",
        name="Aarav Shah",
        phone="+91 98200 41022",
        language="hi",
        segment="retail",
        joined_on="2022-06-14",
    ),
    dict(
        id="CUST-002",
        name="Neha Kulkarni",
        phone="+91 98670 22841",
        language="en",
        segment="retail",
        joined_on="2021-11-02",
    ),
    dict(
        id="CUST-003",
        name="Imran Shaikh",
        phone="+91 99303 77510",
        language="hi",
        segment="retail",
        joined_on="2023-02-27",
    ),
    dict(
        id="CUST-004",
        name="Divya Rao",
        phone="+91 90040 18337",
        language="en",
        segment="premium",
        joined_on="2020-08-19",
    ),
]

# ---------------------------------------------------------------------------
# Merchants
#   MER-1xx  already on Paytm in the demo dataset (transaction counterparties)
#   MER-2xx  Thane prospects for the Grow teammate
#   MER-3xx  out-of-area prospects (excluded by the location filter)
# ---------------------------------------------------------------------------

MERCHANTS = [
    # --- already onboarded (Grow filters these out) ---
    dict(
        id="MER-101",
        name="Demo Cafe",
        category="Cafe",
        location="Thane West",
        paytm_status="active",
        estimated_volume=410000,
        contact="owner@democafe.demo",
        website="democafe.demo",
        notes="Demo merchant, already accepting Paytm.",
    ),
    dict(
        id="MER-102",
        name="Sunrise Grocers",
        category="Grocery",
        location="Thane East",
        paytm_status="active",
        estimated_volume=520000,
        contact="sunrise@grocers.demo",
        website="",
        notes="Demo merchant, already accepting Paytm.",
    ),
    dict(
        id="MER-103",
        name="Metro Pharmacy",
        category="Pharmacy",
        location="Mumbai (Dadar)",
        paytm_status="active",
        estimated_volume=380000,
        contact="care@metropharma.demo",
        website="metropharma.demo",
        notes="Demo merchant, already accepting Paytm.",
    ),
    # --- Thane prospects (12) ---
    dict(
        id="MER-201",
        name="Mumbai Brew House",
        category="Cafe",
        location="Thane West",
        paytm_status="not_onboarded",
        estimated_volume=660000,
        contact="hello@mumbaibrewhouse.demo",
        website="mumbaibrewhouse.demo",
        notes="Three outlets in the demo dataset; card-only at present.",
    ),
    dict(
        id="MER-202",
        name="Vartak Electronics",
        category="Electronics",
        location="Thane West",
        paytm_status="not_onboarded",
        estimated_volume=610000,
        contact="sales@vartakelectronics.demo",
        website="vartakelectronics.demo",
        notes="High average ticket size in the demo dataset.",
    ),
    dict(
        id="MER-203",
        name="Kokan Kitchen",
        category="Restaurant",
        location="Thane (Ghodbunder Road)",
        paytm_status="not_onboarded",
        estimated_volume=540000,
        contact="contact@kokankitchen.demo",
        website="kokankitchen.demo",
        notes="Heavy dinner footfall in the demo dataset.",
    ),
    dict(
        id="MER-204",
        name="Thane Fitness Studio",
        category="Fitness",
        location="Thane West",
        paytm_status="not_onboarded",
        estimated_volume=520000,
        contact="front.desk@thanefitness.demo",
        website="thanefitness.demo",
        notes="Recurring monthly memberships in the demo dataset.",
    ),
    dict(
        id="MER-205",
        name="Shree Bakery",
        category="Bakery",
        location="Thane East",
        paytm_status="not_onboarded",
        estimated_volume=480000,
        contact="+91 98191 30045",
        website="",
        notes="Cash-heavy counter in the demo dataset.",
    ),
    dict(
        id="MER-206",
        name="Lake View Grocers",
        category="Grocery",
        location="Thane (Upvan)",
        paytm_status="not_onboarded",
        estimated_volume=430000,
        contact="+91 98204 77112",
        website="",
        notes="Neighbourhood store in the demo dataset.",
    ),
    dict(
        id="MER-207",
        name="Aarogya Pharmacy",
        category="Pharmacy",
        location="Thane East",
        paytm_status="not_onboarded",
        estimated_volume=350000,
        contact="+91 99670 41288",
        website="",
        notes="Single counter in the demo dataset.",
    ),
    dict(
        id="MER-208",
        name="Rangoli Apparel",
        category="Apparel",
        location="Thane (Majiwada)",
        paytm_status="not_onboarded",
        estimated_volume=300000,
        contact="+91 98333 90217",
        website="",
        notes="Seasonal demand in the demo dataset.",
    ),
    dict(
        id="MER-209",
        name="Ghodbunder Hardware",
        category="Hardware",
        location="Thane (Ghodbunder Road)",
        paytm_status="not_onboarded",
        estimated_volume=240000,
        contact="",
        website="",
        notes="No reachable contact in the demo dataset.",
    ),
    dict(
        id="MER-210",
        name="Style Point Salon",
        category="Salon",
        location="Thane West",
        paytm_status="not_onboarded",
        estimated_volume=180000,
        contact="+91 98920 55401",
        website="",
        notes="Appointment-led business in the demo dataset.",
    ),
    dict(
        id="MER-211",
        name="Page Turner Books",
        category="Bookstore",
        location="Thane West",
        paytm_status="not_onboarded",
        estimated_volume=120000,
        contact="hello@pageturner.demo",
        website="pageturner.demo",
        notes="Low volume, strong online presence in the demo dataset.",
    ),
    dict(
        id="MER-212",
        name="Sai Stationery",
        category="Stationery",
        location="Thane East",
        paytm_status="not_onboarded",
        estimated_volume=90000,
        contact="",
        website="",
        notes="Very small counter in the demo dataset.",
    ),
    # --- out of area (excluded by the location filter) ---
    dict(
        id="MER-301",
        name="Pune Chai Co",
        category="Cafe",
        location="Pune (Kothrud)",
        paytm_status="not_onboarded",
        estimated_volume=580000,
        contact="hi@punechai.demo",
        website="punechai.demo",
        notes="Outside the Thane objective.",
    ),
    dict(
        id="MER-302",
        name="Bandra Bistro",
        category="Restaurant",
        location="Mumbai (Bandra)",
        paytm_status="not_onboarded",
        estimated_volume=720000,
        contact="table@bandrabistro.demo",
        website="bandrabistro.demo",
        notes="Outside the Thane objective.",
    ),
]

# ---------------------------------------------------------------------------
# Transactions
#   TX-1001 / TX-1004 / TX-1007 are the three Resolve demo scenarios.
# ---------------------------------------------------------------------------

TRANSACTIONS = [
    dict(
        id="TX-1001",
        customer_id="CUST-002",
        merchant_id="MER-102",
        amount=500.0,
        payment_method="UPI",
        status="debited_not_settled",
        settlement_status="failed",
        hours_ago=2,
    ),
    dict(
        id="TX-1002",
        customer_id="CUST-001",
        merchant_id="MER-102",
        amount=1250.0,
        payment_method="UPI",
        status="success",
        settlement_status="settled",
        hours_ago=24 * 5,
    ),
    dict(
        id="TX-1003",
        customer_id="CUST-002",
        merchant_id="MER-101",
        amount=340.0,
        payment_method="Paytm Wallet",
        status="success",
        settlement_status="settled",
        hours_ago=24 * 4,
    ),
    dict(
        id="TX-1004",
        customer_id="CUST-001",
        merchant_id="MER-101",
        amount=2000.0,
        payment_method="UPI",
        status="debited_not_settled",
        settlement_status="failed",
        hours_ago=3,
    ),
    dict(
        id="TX-1005",
        customer_id="CUST-001",
        merchant_id="MER-103",
        amount=899.0,
        payment_method="UPI",
        status="success",
        settlement_status="settled",
        hours_ago=24 * 9,
    ),
    dict(
        id="TX-1006",
        customer_id="CUST-003",
        merchant_id="MER-101",
        amount=450.0,
        payment_method="UPI",
        status="success",
        settlement_status="settled",
        hours_ago=24 * 12,
    ),
    dict(
        id="TX-1007",
        customer_id="CUST-003",
        merchant_id="MER-103",
        amount=800.0,
        payment_method="UPI",
        status="debited_not_settled",
        settlement_status="failed",
        hours_ago=24 * 3,
    ),
    dict(
        id="TX-1008",
        customer_id="CUST-004",
        merchant_id="MER-102",
        amount=2100.0,
        payment_method="Paytm Wallet",
        status="success",
        settlement_status="settled",
        hours_ago=24 * 2,
    ),
]

# Prior unresolved cases. These make the "third complaint" in Resolve scenario C
# a fact in the database rather than a claim in the message.
SUPPORT_CASES = [
    dict(
        id="CASE-001",
        customer_id="CUST-003",
        transaction_id="TX-1007",
        issue="₹800 debited, merchant not credited",
        sentiment="negative",
        status="reopened",
        assigned_agent="resolve",
        hours_ago=24 * 3,
    ),
    dict(
        id="CASE-002",
        customer_id="CUST-003",
        transaction_id="TX-1007",
        issue="Follow-up: refund still not received",
        sentiment="negative",
        status="reopened",
        assigned_agent="resolve",
        hours_ago=24,
    ),
]


def seed_database(session: Session) -> None:
    """Insert the demo dataset. Assumes the demo tables are empty."""
    now = utcnow()

    session.add_all([Customer(**row) for row in CUSTOMERS])
    session.add_all([Merchant(**row) for row in MERCHANTS])
    session.add_all(
        [
            Transaction(
                **{k: v for k, v in row.items() if k != "hours_ago"},
                timestamp=now - timedelta(hours=row["hours_ago"]),
            )
            for row in TRANSACTIONS
        ]
    )
    session.add_all(
        [
            SupportCase(
                **{k: v for k, v in row.items() if k != "hours_ago"},
                created_at=now - timedelta(hours=row["hours_ago"]),
            )
            for row in SUPPORT_CASES
        ]
    )
    session.commit()


def reset_demo(session: Session) -> dict[str, int]:
    """Wipe all demo state and restore the seeded dataset.

    Mission history, actions, approvals, events and leads are removed, and the
    simulated Paytm records (including any transaction that was refunded during
    a run) are restored — so the four-minute demo is repeatable end to end.
    Configuration and environment are untouched.
    """
    counts = {
        "missions": session.query(Mission).count(),
        "events": session.query(MissionEvent).count(),
        "approvals": session.query(Approval).count(),
        "actions": session.query(Action).count(),
        "leads": session.query(Lead).count(),
    }

    for model in (MissionEvent, Approval, Action, Lead, Mission):
        session.execute(delete(model))
    for model in (SupportCase, Transaction, Merchant, Customer):
        session.execute(delete(model))
    session.commit()

    seed_database(session)
    return counts


def ensure_seeded(session: Session) -> bool:
    """Seed on first boot. Returns True when seeding actually ran."""
    if session.query(Customer).count() == 0:
        seed_database(session)
        return True
    return False
