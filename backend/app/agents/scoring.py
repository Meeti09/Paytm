"""Explainable lead scoring for the Grow teammate.

Deterministic and fully traceable: every point on the score maps to a named
factor and a one-line reason, so "Lead score 91" can always be broken down in
the UI.

These are demo-dataset signals. They are not Paytm acquisition signals, and
nothing here infers whether a real business accepts Paytm.
"""

from __future__ import annotations

from typing import Any

CATEGORY_FIT: dict[str, int] = {
    "Cafe": 20,
    "Restaurant": 20,
    "Grocery": 18,
    "Electronics": 18,
    "Bakery": 16,
    "Pharmacy": 16,
    "Sweet Shop": 16,
    "Fitness": 14,
    "Apparel": 14,
    "Salon": 12,
    "Hardware": 10,
    "Bookstore": 10,
    "Stationery": 8,
}
DEFAULT_CATEGORY_FIT = 10

VOLUME_BENCHMARK = 900_000  # monthly ₹ that earns the full volume score
MAX_VOLUME_POINTS = 35
MAX_CATEGORY_POINTS = 20
WEBSITE_POINTS = 12
CONTACT_POINTS = 8
LOCATION_POINTS = 15
AVAILABILITY_POINTS = 10


def _inr(value: float) -> str:
    return f"₹{value:,.0f}"


def score_merchant(merchant: dict[str, Any], target_location: str = "") -> dict[str, Any]:
    """Score a merchant prospect out of 100 with a per-factor breakdown."""
    breakdown: list[dict[str, Any]] = []
    reasons: list[str] = []

    # 1. Estimated transaction potential.
    volume = int(merchant.get("estimated_volume") or 0)
    volume_points = min(
        MAX_VOLUME_POINTS, round(volume / VOLUME_BENCHMARK * MAX_VOLUME_POINTS)
    )
    breakdown.append(
        {
            "factor": "Transaction potential",
            "points": volume_points,
            "max": MAX_VOLUME_POINTS,
            "detail": f"{_inr(volume)} estimated monthly volume (demo dataset)",
        }
    )
    if volume_points >= 24:
        reasons.append(f"High estimated transaction potential ({_inr(volume)}/month)")
    elif volume_points >= 14:
        reasons.append(f"Moderate transaction potential ({_inr(volume)}/month)")
    else:
        reasons.append(f"Low estimated volume ({_inr(volume)}/month)")

    # 2. Category fit.
    category = merchant.get("category") or ""
    category_points = CATEGORY_FIT.get(category, DEFAULT_CATEGORY_FIT)
    breakdown.append(
        {
            "factor": "Category fit",
            "points": category_points,
            "max": MAX_CATEGORY_POINTS,
            "detail": f"{category or 'Unclassified'} — digital-payment affinity",
        }
    )
    if category_points >= 16:
        reasons.append(f"{category} is a high-fit category for digital payments")

    # 3. Digital presence / reachability.
    has_website = bool(merchant.get("website"))
    has_contact = bool(merchant.get("contact"))
    digital_points = (WEBSITE_POINTS if has_website else 0) + (
        CONTACT_POINTS if has_contact else 0
    )
    if has_website and has_contact:
        digital_detail = "Website and direct contact available"
        reasons.append("Strong digital presence and a reachable contact")
    elif has_contact:
        digital_detail = "Direct contact available, no website"
        reasons.append("Reachable contact, limited digital presence")
    elif has_website:
        digital_detail = "Website available, no direct contact"
    else:
        digital_detail = "No website and no reachable contact"
        reasons.append("No reachable contact in the demo dataset")
    breakdown.append(
        {
            "factor": "Digital presence",
            "points": digital_points,
            "max": WEBSITE_POINTS + CONTACT_POINTS,
            "detail": digital_detail,
        }
    )

    # 4. Territory match.
    location = merchant.get("location") or ""
    in_territory = (
        not target_location or target_location.strip().lower() in location.lower()
    )
    location_points = LOCATION_POINTS if in_territory else 0
    breakdown.append(
        {
            "factor": "Territory match",
            "points": location_points,
            "max": LOCATION_POINTS,
            "detail": (
                f"{location} matches the mission territory"
                if in_territory
                else f"{location} is outside the mission territory"
            ),
        }
    )
    if in_territory and target_location:
        reasons.append(f"Located in the target territory ({location})")

    # 5. Availability — already-onboarded merchants score nothing here.
    onboarded = merchant.get("paytm_status") == "active"
    availability_points = 0 if onboarded else AVAILABILITY_POINTS
    breakdown.append(
        {
            "factor": "Availability",
            "points": availability_points,
            "max": AVAILABILITY_POINTS,
            "detail": (
                "Already accepting Paytm in the demo dataset"
                if onboarded
                else "Not onboarded in the demo dataset"
            ),
        }
    )
    if not onboarded:
        reasons.append("Not onboarded in the demo dataset")

    score = sum(item["points"] for item in breakdown)
    if score >= 80:
        opportunity = "High"
    elif score >= 65:
        opportunity = "Medium"
    else:
        opportunity = "Low"

    return {
        "score": int(score),
        "breakdown": breakdown,
        "reasons": reasons,
        "opportunity": opportunity,
    }
