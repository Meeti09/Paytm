"""Grow — the Merchant Acquisition teammate.

Mission: find, qualify, approach and move high-potential merchants toward Paytm
onboarding.

    MISSION_CREATED -> DISCOVERING -> ENRICHING -> SCORING -> PRIORITIZING
    -> OUTREACH -> WAITING_RESPONSE -> QUALIFYING -> SALES_READY
    -> MEETING_BOOKED -> COMPLETED

Grow's actions run through the same policy engine as Resolve's. Outreach is a
CONTROLLED tool on a simulated channel: no message leaves this machine.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.scoring import score_merchant
from app.config import settings
from app.integrations.cognee import cognee
from app.integrations.llm import LLMUnavailable, llm
from app.integrations.paytm_mock import MockPaytmAdapter
from app.models.models import Lead, utcnow
from app.policy.risk import ActionProposal
from app.services.mission_service import next_sequence_id, update_mission

log = logging.getLogger("pulse.grow")

paytm = MockPaytmAdapter()

STAGE_RANK = {
    "discovered": 1,
    "scored": 2,
    "disqualified": 2,
    "qualified": 3,
    "contacted": 4,
    "responded": 5,
    "sales_ready": 6,
    "meeting_booked": 7,
}

PROGRESS = {
    "DISCOVERING": 12,
    "ENRICHING": 26,
    "SCORING": 42,
    "PRIORITIZING": 54,
    "OUTREACH": 68,
    "WAITING_RESPONSE": 78,
    "QUALIFYING": 86,
    "SALES_READY": 92,
    "MEETING_BOOKED": 100,
}

SUGGESTED_REPLIES = [
    "Interested. What do I need to do?",
    "Not interested right now, thanks.",
]

OUTREACH_TEMPLATE = (
    "Hi {name} team — this is Paytm reaching out about payments at your "
    "{category_lower} in {location}. {hook} A Paytm QR and Soundbox would let you "
    "accept UPI, cards and wallet in one place with same-day settlement and "
    "instant audio confirmation. Could I show you the setup — it takes about "
    "ten minutes?"
)


def inr(value: float) -> str:
    return f"₹{value:,.0f}"


class GrowAgent(BaseAgent):
    agent = "grow"

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    async def run(self, session: Session) -> None:
        self.bind(session)
        mission = self.guard(session)
        inputs = mission.inputs or {}
        territory: str = inputs.get("location", "Thane")
        target_count: int = int(inputs.get("target_count", 5))
        category: str = inputs.get("category", "")

        self.emit(session, "MISSION_STARTED", "Mission accepted by Grow")
        self.advance(
            session, stage="DISCOVERING", progress=PROGRESS["DISCOVERING"], status="running"
        )
        await self.beat()

        # --- WF4: discover, filter, enrich, score, rank ----------------
        result = await self.n8n_run(
            "lead-discovery",
            {
                "mission_id": self.mission_id,
                "location": territory,
                "category": category,
                "target_count": target_count,
            },
            self._wf_lead_discovery,
        )
        if not result.success:
            self.needs_attention(
                session, f"Lead discovery workflow failed: {result.error}"
            )
            return

        data = result.data
        prospects: list[dict] = data["prospects"]
        skipped: list[dict] = data["skipped_onboarded"]

        self.emit(
            session,
            "LEAD_DISCOVERED",
            f"{data['matched']} merchants match '{territory}' in the demo dataset · "
            f"{len(skipped)} already on Paytm (skipped) · "
            f"{len(prospects)} prospects to evaluate",
            meta={
                "matched": data["matched"],
                "skipped": [m["name"] for m in skipped],
                "prospects": len(prospects),
            },
        )
        await self.beat()

        if not prospects:
            self.emit(session, "MISSION_COMPLETED", "No prospects found in this territory")
            self.advance(
                session,
                stage="COMPLETED",
                progress=100,
                status="completed",
                result="no_qualified_leads",
                result_label="No prospects found in this territory",
            )
            return

        # Enrichment (demo dataset + memory).
        self.advance(session, stage="ENRICHING", progress=PROGRESS["ENRICHING"])
        memory = await cognee.recall(
            scope="merchant",
            subject_id=territory,
            query=f"merchant observations in {territory}",
            local_context=[
                {
                    "label": "Territory",
                    "value": f"{len(prospects)} unonboarded prospects on record",
                    "kind": "profile",
                }
            ],
        )
        self.emit(
            session,
            "MEMORY_RETRIEVED",
            f"Context memory: {len(memory['items'])} items ({memory['detail']})",
            meta={"source": memory["source"]},
        )
        await self.beat(0.7)

        # Persist leads.
        self.advance(session, stage="SCORING", progress=PROGRESS["SCORING"])
        leads = self._persist_leads(session, prospects)

        qualification_threshold = settings.lead_qualification_threshold
        for lead_row, prospect in list(zip(leads, prospects))[:5]:
            self.emit(
                session,
                "LEAD_SCORED",
                f"{prospect['merchant']['name']} — lead score {prospect['score']} "
                f"({prospect['opportunity']} opportunity)",
                meta={
                    "lead_id": lead_row.id,
                    "merchant_id": prospect["merchant"]["id"],
                    "score": prospect["score"],
                    "reasons": prospect["reasons"],
                },
            )
            await self.beat(0.35)

        self._refresh_context(session, territory, target_count)
        qualified = [p for p in prospects if p["score"] >= qualification_threshold]
        self.emit(
            session,
            "LEAD_SCORED",
            f"{len(prospects)} merchants scored · {len(qualified)} above the "
            f"qualification threshold of {qualification_threshold}",
            meta={
                "evaluated": len(prospects),
                "qualified": len(qualified),
                "threshold": qualification_threshold,
            },
        )
        await self.beat()

        # --- Prioritise -------------------------------------------------
        self.advance(session, stage="PRIORITIZING", progress=PROGRESS["PRIORITIZING"])
        outreach_threshold = settings.lead_outreach_threshold
        contactable = [
            p
            for p in qualified
            if p["score"] >= outreach_threshold and p["merchant"].get("contact")
        ][:target_count]

        self.emit(
            session,
            "LEAD_QUALIFIED",
            f"{len(qualified)} qualified · {len(contactable)} ready for outreach "
            f"(score ≥ {outreach_threshold} with a reachable contact)",
            meta={"qualified": len(qualified), "for_outreach": len(contactable)},
        )
        await self.beat()

        if not contactable:
            self._refresh_context(session, territory, target_count)
            self.emit(
                session, "MISSION_COMPLETED", "No merchant met the outreach bar"
            )
            self.advance(
                session,
                stage="COMPLETED",
                progress=100,
                status="completed",
                result="no_qualified_leads",
                result_label=f"{len(qualified)} qualified, none met the outreach bar",
            )
            return

        # --- Outreach (policy-governed) ---------------------------------
        self.advance(session, stage="OUTREACH", progress=PROGRESS["OUTREACH"])

        proposal = ActionProposal(
            action_type="send_outreach",
            description=f"Send onboarding outreach to {len(contactable)} merchants",
            subject=", ".join(p["merchant"]["name"] for p in contactable),
            money_amount=0.0,
            affects_account=False,
            irreversible=False,
            sentiment="neutral",
            evidence=[
                f"{p['merchant']['name']} — score {p['score']}, {p['opportunity']} opportunity"
                for p in contactable
            ],
            impact="Personalised outreach is sent on the simulated demo channel.",
            payload={
                "lead_ids": [
                    self._lead_for_merchant(session, p["merchant"]["id"]).id
                    for p in contactable
                ],
                "channel": "simulated",
            },
        )
        action, risk = self.propose(session, proposal)

        decision_card = {
            "title": f"Contact {len(contactable)} high-opportunity merchants",
            "action_type": "send_outreach",
            "amount": 0.0,
            "reason": (
                f"{len(qualified)} of {len(prospects)} prospects cleared the "
                f"qualification threshold of {qualification_threshold}. "
                f"{len(contactable)} of those score {outreach_threshold}+ and have a "
                "reachable contact, so they go first."
            ),
            "evidence": proposal.evidence,
            "risk_level": risk.risk_level,
            "verdict": risk.verdict,
            "policy_rule": risk.primary_rule,
            "policy_detail": risk.policy_detail,
            "triggered_rules": [
                {"rule": t.rule, "detail": t.detail, "risk": t.risk}
                for t in risk.triggered
            ],
            "next": (
                "Human approval required."
                if risk.requires_approval
                else "Sending on the simulated channel."
            ),
            "source": "deterministic_reasoner",
            "action_id": action.id,
        }
        update_mission(session, self.mission(session), decision=decision_card)

        if risk.requires_approval:
            approval = self.request_approval(session, action, proposal, risk)
            self.advance(
                session,
                stage="WAITING_APPROVAL",
                progress=PROGRESS["OUTREACH"],
                status="waiting_approval",
                summary={
                    "headline": "Outreach waiting for human approval",
                    "approval_id": approval.id,
                },
            )
            return

        await self._send_outreach(session, action, contactable, territory, target_count)

    # ------------------------------------------------------------------
    # WF4 — Lead discovery
    # ------------------------------------------------------------------

    async def _wf_lead_discovery(self, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._session
        location = payload.get("location", "")
        category = payload.get("category", "")

        matched = paytm.search_merchants(session, location=location, category=category)
        skipped_onboarded = [m for m in matched if m["paytm_status"] == "active"]
        candidates = [m for m in matched if m["paytm_status"] != "active"]

        prospects = []
        for merchant in candidates:
            scored = score_merchant(merchant, location)
            prospects.append(
                {
                    "merchant": merchant,
                    "score": scored["score"],
                    "breakdown": scored["breakdown"],
                    "reasons": scored["reasons"],
                    "opportunity": scored["opportunity"],
                }
            )
        prospects.sort(key=lambda p: p["score"], reverse=True)

        return {
            "success": True,
            "matched": len(matched),
            "skipped_onboarded": skipped_onboarded,
            "prospects": prospects,
        }

    def _persist_leads(self, session: Session, prospects: list[dict]) -> list[Lead]:
        threshold = settings.lead_qualification_threshold
        leads: list[Lead] = []
        for prospect in prospects:
            merchant = prospect["merchant"]
            qualified = prospect["score"] >= threshold
            stage = "qualified" if qualified else "scored"
            lead = Lead(
                id=next_sequence_id(session, Lead, "L"),
                mission_id=self.mission_id,
                merchant_id=merchant["id"],
                score=prospect["score"],
                stage=stage,
                stage_rank=STAGE_RANK[stage],
                reason=prospect["reasons"],
                score_breakdown=prospect["breakdown"],
                next_action=(
                    "Start merchant conversation"
                    if qualified
                    else "Hold — below the qualification threshold"
                ),
            )
            session.add(lead)
            session.commit()
            session.refresh(lead)
            leads.append(lead)
        return leads

    # ------------------------------------------------------------------
    # WF5 — Outreach
    # ------------------------------------------------------------------

    async def _send_outreach(
        self,
        session: Session,
        action,
        contactable: list[dict],
        territory: str,
        target_count: int,
    ) -> None:
        messages: dict[str, str] = {}
        for prospect in contactable:
            lead = self._lead_for_merchant(session, prospect["merchant"]["id"])
            messages[lead.id] = await self._compose_outreach(prospect)

        result = await self.execute(
            session,
            action,
            workflow="outreach",
            payload={
                "mission_id": self.mission_id,
                "agent": self.agent,
                "action_id": action.id,
                "channel": "simulated",
                "messages": messages,
            },
            local_handler=self._wf_outreach,
        )
        if not result.success:
            self.needs_attention(session, f"Outreach workflow failed: {result.error}")
            return

        for prospect in contactable:
            lead = self._lead_for_merchant(session, prospect["merchant"]["id"])
            self.emit(
                session,
                "LEAD_CONTACTED",
                f"Outreach sent to {prospect['merchant']['name']} "
                f"(simulated channel · {prospect['merchant']['contact']})",
                meta={
                    "lead_id": lead.id,
                    "merchant_id": prospect["merchant"]["id"],
                    "message": messages.get(lead.id, ""),
                },
            )
            await self.beat(0.4)

        focus_lead = self._lead_for_merchant(session, contactable[0]["merchant"]["id"])
        self._refresh_context(
            session, territory, target_count, focus_lead_id=focus_lead.id
        )
        self.advance(
            session,
            stage="WAITING_RESPONSE",
            progress=PROGRESS["WAITING_RESPONSE"],
            status="waiting_response",
            summary={
                "headline": f"{len(contactable)} merchants contacted — awaiting replies",
                "focus_lead_id": focus_lead.id,
                "suggested_replies": SUGGESTED_REPLIES,
            },
        )

    async def _wf_outreach(self, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._session
        sent = []
        for lead_id, message in (payload.get("messages") or {}).items():
            lead = session.get(Lead, lead_id)
            if lead is None:
                continue
            lead.outreach_message = message
            lead.outreach_channel = payload.get("channel", "simulated")
            lead.stage = "contacted"
            lead.stage_rank = STAGE_RANK["contacted"]
            lead.next_action = "Await merchant response"
            lead.updated_at = utcnow()
            session.add(lead)
            sent.append(lead_id)
        session.commit()
        return {"success": True, "sent": sent, "delivery": "simulated"}

    async def _compose_outreach(self, prospect: dict) -> str:
        merchant = prospect["merchant"]
        hook = prospect["reasons"][0] if prospect["reasons"] else ""
        fallback = OUTREACH_TEMPLATE.format(
            name=merchant["name"],
            category_lower=merchant["category"].lower(),
            location=merchant["location"],
            hook=f"{hook}." if hook and not hook.endswith(".") else hook,
        )
        if not llm.configured:
            return fallback
        try:
            parsed = await llm.complete_json(
                system=(
                    "You are Grow, a merchant acquisition teammate for Paytm. "
                    "Write short, specific, non-hyped outreach. No emoji, no "
                    "exclamation marks, no invented statistics. "
                    "Reply with a single JSON object and no other text."
                ),
                user=(
                    f"Merchant: {merchant['name']}\n"
                    f"Category: {merchant['category']}\n"
                    f"Location: {merchant['location']}\n"
                    f"Estimated monthly volume (demo dataset): "
                    f"{inr(merchant['estimated_volume'])}\n"
                    f"Why selected: {'; '.join(prospect['reasons'])}\n\n"
                    'Respond as {"message": a 3-sentence outreach message under 400 '
                    "characters that references this specific business}"
                ),
                required_keys=("message",),
                max_tokens=400,
            )
            message = str(parsed["message"]).strip()
            return message[:400] if message else fallback
        except LLMUnavailable as exc:
            log.warning("Outreach drafting fell back to template: %s", exc)
            return fallback

    # ------------------------------------------------------------------
    # Merchant reply -> qualification -> meeting (WF5 + WF6)
    # ------------------------------------------------------------------

    async def handle_reply(
        self, session: Session, lead_id: str, reply_text: str
    ) -> None:
        self.bind(session)
        mission = self.guard(session)
        lead = session.get(Lead, lead_id)
        if lead is None:
            self.emit(session, "SYSTEM_WARNING", f"Lead {lead_id} not found", level="error")
            return

        merchant = paytm.get_merchant(session, lead.merchant_id)
        lead.response_message = reply_text
        lead.stage = "responded"
        lead.stage_rank = STAGE_RANK["responded"]
        lead.updated_at = utcnow()
        session.add(lead)
        session.commit()

        update_mission(
            session,
            mission,
            status="running",
            stage="QUALIFYING",
            progress=PROGRESS["QUALIFYING"],
        )
        self.emit(
            session,
            "LEAD_RESPONDED",
            f"{merchant['name']} replied: “{reply_text.strip()[:140]}”",
            meta={"lead_id": lead.id, "merchant_id": merchant["id"]},
        )
        await self.beat()

        verdict = await self._qualify_reply(reply_text, merchant)
        lead.qualification_note = verdict["note"]

        territory = (mission.inputs or {}).get("location", "")
        target_count = int((mission.inputs or {}).get("target_count", 5))

        if not verdict["interested"]:
            lead.stage = "disqualified"
            lead.stage_rank = STAGE_RANK["disqualified"]
            lead.next_action = "Re-approach next quarter"
            lead.updated_at = utcnow()
            session.add(lead)
            session.commit()

            self.emit(
                session,
                "LEAD_QUALIFIED",
                f"{merchant['name']} is not interested — parked for a later cycle",
                level="warn",
                meta={"lead_id": lead.id, "note": verdict["note"]},
            )
            self._refresh_context(session, territory, target_count, focus_lead_id=lead.id)
            self.emit(
                session,
                "MISSION_COMPLETED",
                "Mission complete — no merchant reached sales-ready in this cycle",
            )
            self.advance(
                session,
                stage="COMPLETED",
                progress=100,
                status="completed",
                result="no_qualified_leads",
                result_label="Contacted, no sales-ready merchant this cycle",
            )
            return

        lead.stage = "sales_ready"
        lead.stage_rank = STAGE_RANK["sales_ready"]
        lead.next_action = "Book onboarding meeting"
        lead.updated_at = utcnow()
        session.add(lead)
        session.commit()

        self.emit(
            session,
            "LEAD_QUALIFIED",
            f"{merchant['name']} qualified as sales-ready — {verdict['note']}",
            meta={"lead_id": lead.id, "note": verdict["note"]},
        )
        self.advance(session, stage="SALES_READY", progress=PROGRESS["SALES_READY"])
        await self.beat()

        # --- WF6: book the meeting (policy-governed) --------------------
        slot = self._next_slot()
        proposal = ActionProposal(
            action_type="book_meeting",
            description=f"Book onboarding meeting with {merchant['name']}",
            subject=f"{merchant['name']} · {slot}",
            money_amount=0.0,
            affects_account=False,
            irreversible=False,
            evidence=[
                f"Lead score {lead.score} ({merchant['category']}, {merchant['location']})",
                f"Merchant replied: “{reply_text.strip()[:120]}”",
                verdict["note"],
            ],
            impact="A simulated onboarding meeting is booked and the lead moves to meeting_booked.",
            payload={"lead_id": lead.id, "slot": slot},
        )
        action, risk = self.propose(session, proposal)

        update_mission(
            session,
            self.mission(session),
            decision={
                "title": f"Book onboarding meeting — {merchant['name']}",
                "action_type": "book_meeting",
                "amount": 0.0,
                "reason": verdict["note"],
                "evidence": proposal.evidence,
                "risk_level": risk.risk_level,
                "verdict": risk.verdict,
                "policy_rule": risk.primary_rule,
                "policy_detail": risk.policy_detail,
                "triggered_rules": [
                    {"rule": t.rule, "detail": t.detail, "risk": t.risk}
                    for t in risk.triggered
                ],
                "next": (
                    "Human approval required."
                    if risk.requires_approval
                    else "Booking on the simulated calendar."
                ),
                "source": verdict["source"],
                "action_id": action.id,
            },
        )

        if risk.requires_approval:
            approval = self.request_approval(session, action, proposal, risk)
            self.advance(
                session,
                stage="WAITING_APPROVAL",
                progress=PROGRESS["SALES_READY"],
                status="waiting_approval",
                summary={
                    "headline": "Meeting booking waiting for human approval",
                    "approval_id": approval.id,
                },
            )
            return

        await self._book_meeting(session, action, lead.id, territory, target_count)

    async def _book_meeting(
        self,
        session: Session,
        action,
        lead_id: str,
        territory: str,
        target_count: int,
    ) -> None:
        lead = session.get(Lead, lead_id)
        merchant = paytm.get_merchant(session, lead.merchant_id)

        result = await self.execute(
            session,
            action,
            workflow="followup",
            payload={
                "mission_id": self.mission_id,
                "agent": self.agent,
                "action_id": action.id,
                "lead_id": lead_id,
                "slot": (action.payload or {}).get("slot", self._next_slot()),
                "attendee": merchant.get("contact", ""),
            },
            local_handler=self._wf_followup,
        )
        if not result.success:
            self.needs_attention(session, f"Meeting booking failed: {result.error}")
            return

        booking = result.data.get("booking", {})
        self.emit(
            session,
            "MEETING_BOOKED",
            f"Onboarding meeting booked with {merchant['name']} — {booking.get('slot')}",
            meta={"lead_id": lead_id, **booking},
        )
        await self.beat(0.6)

        self._refresh_context(session, territory, target_count, focus_lead_id=lead_id)
        mission = self.mission(session)
        stats = (mission.context or {}).get("stats", {})

        decision_card = dict(mission.decision or {})
        decision_card["resolved"] = True
        decision_card["next"] = f"Meeting booked for {booking.get('slot', '')}."

        self.emit(
            session, "MISSION_COMPLETED", f"Mission complete — meeting booked with {merchant['name']}"
        )
        self.advance(
            session,
            stage="MEETING_BOOKED",
            progress=PROGRESS["MEETING_BOOKED"],
            status="completed",
            result="meeting_booked",
            result_label=f"Meeting booked with {merchant['name']}",
            decision=decision_card,
            summary={
                "headline": f"Onboarding meeting booked with {merchant['name']}",
                "lines": [
                    f"{stats.get('evaluated', 0)} merchants evaluated",
                    f"{stats.get('qualified', 0)} qualified · "
                    f"{stats.get('contacted', 0)} contacted",
                    f"1 sales-ready · meeting {booking.get('slot', '')}",
                ],
                "meeting_slot": booking.get("slot"),
                "merchant": merchant["name"],
            },
        )

    async def _wf_followup(self, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._session
        booking = paytm.book_meeting(
            session,
            payload["lead_id"],
            payload["slot"],
            payload.get("attendee", ""),
        )
        if not booking.get("success"):
            return {"success": False, "error": booking.get("error", "BOOKING_FAILED")}

        lead = session.get(Lead, payload["lead_id"])
        lead.stage = "meeting_booked"
        lead.stage_rank = STAGE_RANK["meeting_booked"]
        lead.next_action = "Run onboarding session"
        lead.updated_at = utcnow()
        session.add(lead)

        onboarding = paytm.submit_onboarding(session, lead.merchant_id)
        session.commit()
        return {"success": True, "booking": booking, "onboarding": onboarding}

    async def _qualify_reply(self, text: str, merchant: dict) -> dict[str, Any]:
        low = text.lower()
        negative = any(
            marker in low
            for marker in (
                "not interested",
                "no thanks",
                "no thank",
                "don't want",
                "dont want",
                "नहीं चाहिए",
                "रुचि नहीं",
                "later",
                "busy",
            )
        )
        positive = any(
            marker in low
            for marker in (
                "interested",
                "yes",
                "what do i need",
                "how do i",
                "how much",
                "sign me",
                "tell me more",
                "क्या करना",
                "कैसे",
                "चाहिए",
                "ठीक है",
            )
        )
        interested = positive and not negative
        note = (
            f"Merchant expressed intent and asked about next steps; "
            f"{merchant['name']} moves to sales-ready."
            if interested
            else "Merchant declined for this cycle."
        )
        result = {"interested": interested, "note": note, "source": "deterministic_reasoner"}

        if not llm.configured:
            return result
        try:
            parsed = await llm.complete_json(
                system=(
                    "You qualify merchant replies for a Paytm acquisition workflow. "
                    "Reply with a single JSON object and no other text."
                ),
                user=(
                    f"Merchant: {merchant['name']} ({merchant['category']})\n"
                    f"Reply: {text}\n\n"
                    '{"interested": true or false, "note": one short sentence '
                    "explaining the qualification decision}"
                ),
                required_keys=("interested",),
                max_tokens=200,
            )
            if isinstance(parsed.get("interested"), bool):
                result["interested"] = parsed["interested"]
            if isinstance(parsed.get("note"), str) and parsed["note"].strip():
                result["note"] = parsed["note"].strip()[:240]
            result["source"] = f"llm:{llm.label}"
        except LLMUnavailable as exc:
            log.warning("Reply qualification fell back to rules: %s", exc)
        return result

    # ------------------------------------------------------------------
    # Approval continuations
    # ------------------------------------------------------------------

    async def continue_after_approval(self, session: Session, approval, reviewer: str) -> None:
        self.bind(session)
        mission = self.mission(session)
        update_mission(session, mission, human_involved=True, status="running")

        from app.models.models import Action  # local import avoids a cycle at module load

        action = session.get(Action, approval.action_id)
        if action is None:
            self.fail_mission(session, "Approved action no longer exists.")
            return
        action.status = "proposed"
        session.add(action)
        session.commit()

        territory = (mission.inputs or {}).get("location", "")
        target_count = int((mission.inputs or {}).get("target_count", 5))

        if action.action_type == "book_meeting":
            await self._book_meeting(
                session, action, (action.payload or {})["lead_id"], territory, target_count
            )
            return

        contactable = self._contactable_from_payload(session, action.payload or {})
        await self._send_outreach(session, action, contactable, territory, target_count)

    async def continue_after_rejection(self, session: Session, approval, reviewer: str) -> None:
        self.bind(session)
        mission = self.mission(session)
        self.emit(
            session,
            "MISSION_COMPLETED",
            f"Mission stopped — {approval.title} rejected by {reviewer}",
            level="warn",
        )
        update_mission(
            session,
            mission,
            status="completed",
            stage="COMPLETED",
            progress=100,
            human_involved=True,
            result="rejected_by_human",
            result_label=f"Rejected by {reviewer}",
            summary={"headline": f"{approval.title} rejected by {reviewer}", "lines": []},
        )

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def _lead_for_merchant(self, session: Session, merchant_id: str) -> Lead:
        return session.scalars(
            select(Lead)
            .where(Lead.mission_id == self.mission_id)
            .where(Lead.merchant_id == merchant_id)
        ).first()

    def _contactable_from_payload(
        self, session: Session, payload: dict[str, Any]
    ) -> list[dict]:
        contactable = []
        for lead_id in payload.get("lead_ids", []):
            lead = session.get(Lead, lead_id)
            if lead is None:
                continue
            merchant = paytm.get_merchant(session, lead.merchant_id)
            contactable.append(
                {
                    "merchant": merchant,
                    "score": lead.score,
                    "reasons": lead.reason or [],
                    "opportunity": "High" if lead.score >= 80 else "Medium",
                }
            )
        return contactable

    def _refresh_context(
        self,
        session: Session,
        territory: str,
        target_count: int,
        *,
        focus_lead_id: str | None = None,
    ) -> None:
        leads = list(
            session.scalars(
                select(Lead)
                .where(Lead.mission_id == self.mission_id)
                .order_by(Lead.score.desc())
            )
        )
        lead_views = []
        for lead in leads:
            merchant = paytm.get_merchant(session, lead.merchant_id) or {}
            lead_views.append(
                {
                    "id": lead.id,
                    "merchant_id": lead.merchant_id,
                    "name": merchant.get("name", lead.merchant_id),
                    "category": merchant.get("category", ""),
                    "location": merchant.get("location", ""),
                    "paytm_status": merchant.get("paytm_status", ""),
                    "estimated_volume": merchant.get("estimated_volume", 0),
                    "contact": merchant.get("contact", ""),
                    "website": merchant.get("website", ""),
                    "score": lead.score,
                    "stage": lead.stage,
                    "opportunity": "High"
                    if lead.score >= 80
                    else ("Medium" if lead.score >= 65 else "Low"),
                    "reasons": lead.reason or [],
                    "breakdown": lead.score_breakdown or [],
                    "next_action": lead.next_action,
                    "outreach_message": lead.outreach_message,
                    "response_message": lead.response_message,
                    "qualification_note": lead.qualification_note,
                    "meeting_slot": lead.meeting_slot,
                }
            )

        stats = {
            "evaluated": len(leads),
            "qualified": sum(1 for lead in leads if lead.stage_rank >= STAGE_RANK["qualified"]),
            "contacted": sum(1 for lead in leads if lead.stage_rank >= STAGE_RANK["contacted"]),
            "responded": sum(1 for lead in leads if lead.stage_rank >= STAGE_RANK["responded"]),
            "sales_ready": sum(
                1 for lead in leads if lead.stage_rank >= STAGE_RANK["sales_ready"]
            ),
            "meetings_booked": sum(
                1 for lead in leads if lead.stage_rank >= STAGE_RANK["meeting_booked"]
            ),
        }

        focus = next((lv for lv in lead_views if lv["id"] == focus_lead_id), None)
        panels = [
            {
                "title": "Objective",
                "rows": [
                    {"label": "Territory", "value": territory or "All"},
                    {"label": "Target", "value": f"{target_count} merchants"},
                    {
                        "label": "Qualification",
                        "value": f"Score ≥ {settings.lead_qualification_threshold}",
                    },
                    {
                        "label": "Outreach bar",
                        "value": f"Score ≥ {settings.lead_outreach_threshold}",
                    },
                ],
            },
            {
                "title": "Pipeline",
                "rows": [
                    {"label": "Evaluated", "value": str(stats["evaluated"])},
                    {"label": "Qualified", "value": str(stats["qualified"])},
                    {"label": "Contacted", "value": str(stats["contacted"])},
                    {"label": "Sales-ready", "value": str(stats["sales_ready"])},
                ],
            },
        ]
        if focus:
            panels.append(
                {
                    "title": "Top merchant",
                    "rows": [
                        {"label": "Name", "value": focus["name"]},
                        {"label": "Category", "value": focus["category"]},
                        {"label": "Location", "value": focus["location"]},
                        {
                            "label": "Paytm status",
                            "value": "Not onboarded"
                            if focus["paytm_status"] != "active"
                            else "Active",
                        },
                        {"label": "Lead score", "value": f"{focus['score']} / 100"},
                        {"label": "Opportunity", "value": focus["opportunity"]},
                    ],
                }
            )

        update_mission(
            session,
            self.mission(session),
            context={
                "kind": "grow",
                "territory": territory,
                "target_count": target_count,
                "stats": stats,
                "leads": lead_views,
                "focus_lead_id": focus_lead_id,
                "suggested_replies": SUGGESTED_REPLIES,
                "panels": panels,
            },
        )

    @staticmethod
    def _next_slot() -> str:
        slot = utcnow() + timedelta(days=1)
        return f"{slot.strftime('%a %d %b')}, 11:00 AM IST"
