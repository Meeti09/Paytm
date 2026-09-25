"""Resolve — the Customer Resolution teammate.

Mission: own a customer issue until it is verified as resolved.

    RECEIVED -> UNDERSTANDING -> CONTEXT_LOADING -> INVESTIGATING -> DECISION
    -> RISK_CHECK -> (EXECUTING -> VERIFYING -> RESOLVED)
                  \\-> WAITING_APPROVAL -> APPROVED/REJECTED -> ...

The model proposes the action and writes the customer-facing wording. The refund
amount always comes from the transaction ledger, and permission to execute always
comes from the policy engine.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.integrations.cognee import cognee
from app.integrations.llm import LLMUnavailable, llm
from app.integrations.paytm_mock import MockPaytmAdapter
from app.integrations.sarvam import sarvam
from app.models.models import Action, Approval
from app.policy.risk import ActionProposal
from app.services.event_service import publish_approvals_changed
from app.services.mission_service import update_mission

log = logging.getLogger("pulse.resolve")

paytm = MockPaytmAdapter()

ALLOWED_ACTIONS = {"refund", "escalate_to_specialist", "notify_customer"}

PROGRESS = {
    "UNDERSTANDING": 12,
    "CONTEXT_LOADING": 28,
    "INVESTIGATING": 46,
    "DECISION": 64,
    "RISK_CHECK": 74,
    "WAITING_APPROVAL": 80,
    "EXECUTING": 88,
    "VERIFYING": 94,
    "RESOLVED": 100,
}

CUSTOMER_TEMPLATES = {
    "refund_en": (
        "Hi {name}, we checked transaction {tx}. {amount} was debited but the "
        "merchant settlement did not complete, so we have refunded {amount} to "
        "your source account. Sorry for the trouble. — Paytm Pulse"
    ),
    "refund_hi": (
        "नमस्ते {name}, हमने ट्रांज़ैक्शन {tx} जाँच लिया है। {amount} कट गया था लेकिन "
        "merchant को settlement नहीं हुआ, इसलिए {amount} आपके source account में "
        "वापस कर दिया गया है। असुविधा के लिए खेद है। — Paytm Pulse"
    ),
    "escalate_en": (
        "Hi {name}, we have reviewed transaction {tx} and assigned it to a "
        "specialist who will contact you directly. Reference {case}. — Paytm Pulse"
    ),
    "escalate_hi": (
        "नमस्ते {name}, हमने ट्रांज़ैक्शन {tx} की समीक्षा की है और इसे एक specialist को "
        "सौंप दिया गया है जो आपसे सीधे संपर्क करेंगे। Reference {case}. — Paytm Pulse"
    ),
}


def inr(value: float) -> str:
    return f"₹{value:,.0f}"


class ResolveAgent(BaseAgent):
    agent = "resolve"

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    async def run(self, session: Session) -> None:
        self.bind(session)
        mission = self.guard(session)
        inputs = mission.inputs or {}
        message: str = inputs.get("message", "")
        customer_id: str = inputs.get("customer_id", "")

        self.emit(session, "MISSION_STARTED", "Mission accepted by Resolve")
        self.advance(
            session, stage="UNDERSTANDING", progress=PROGRESS["UNDERSTANDING"], status="running"
        )
        await self.beat()

        # --- WF1: understand the message ------------------------------
        intake = await self._run_intake(session, message)
        if intake is None:
            return
        await self.beat()

        # --- WF2: load context ----------------------------------------
        self.advance(session, stage="CONTEXT_LOADING", progress=PROGRESS["CONTEXT_LOADING"])
        evidence = await self._run_investigation(
            session, customer_id=customer_id, intake=intake
        )
        if evidence is None:
            return
        await self.beat()

        # --- Decide ----------------------------------------------------
        self.guard(session)
        self.advance(session, stage="DECISION", progress=PROGRESS["DECISION"])
        decision = await self._generate_decision(session, intake, evidence)
        if decision is None:
            return  # mission paused — reasoning unavailable
        await self.beat()

        # --- Risk check + route ----------------------------------------
        self.guard(session)
        self.advance(session, stage="RISK_CHECK", progress=PROGRESS["RISK_CHECK"])
        await self._route_decision(session, intake, evidence, decision)

    async def retry(self, session: Session) -> None:
        """Resume a mission that stopped on a recoverable error.

        If context was already gathered, pick up at the decision step instead of
        re-investigating from scratch. A re-proposed action is re-judged by the
        policy engine, so a retry can never skip an approval that is still due.
        """
        self.bind(session)
        mission = self.mission(session)
        context = mission.context or {}
        update_mission(session, mission, status="running", error="")

        if not (context.get("transaction") and context.get("customer")):
            await self.run(session)
            return

        self.emit(session, "MISSION_RESUMED", "Retrying from the decision step")
        evidence = self._evidence_from_context(session, context)
        intake = context.get("intake", {})

        self.advance(session, stage="DECISION", progress=PROGRESS["DECISION"])
        decision = await self._generate_decision(session, intake, evidence)
        if decision is None:
            return
        await self.beat()
        self.advance(session, stage="RISK_CHECK", progress=PROGRESS["RISK_CHECK"])
        await self._route_decision(session, intake, evidence, decision)

    # ------------------------------------------------------------------
    # WF1 — Customer Issue Intake
    # ------------------------------------------------------------------

    async def _run_intake(self, session: Session, message: str) -> dict[str, Any] | None:
        result = await self.n8n_run(
            "issue-intake",
            {"mission_id": self.mission_id, "message": message},
            self._wf_issue_intake,
        )
        if not result.success:
            self.needs_attention(session, f"Issue intake workflow failed: {result.error}")
            return None

        analysis = result.data.get("analysis", {})
        lang_source = "Sarvam" if analysis.get("source") == "sarvam" else "local classifier"
        self.emit(
            session,
            "LANGUAGE_DETECTED",
            f"Language detected: {analysis.get('language_name', 'Unknown')} "
            f"({analysis.get('script', '')}) via {lang_source}",
            meta={
                "language": analysis.get("language"),
                "script": analysis.get("script"),
                "source": analysis.get("source"),
            },
        )
        await self.beat(0.6)
        self.emit(
            session,
            "INTENT_CLASSIFIED",
            f"Intent: {analysis.get('intent_label', analysis.get('intent'))} · "
            f"sentiment {analysis.get('sentiment', 'neutral').replace('_', ' ')}",
            level="warn" if analysis.get("sentiment") == "strongly_negative" else "ok",
            meta=analysis,
        )
        return analysis

    async def _wf_issue_intake(self, payload: dict[str, Any]) -> dict[str, Any]:
        analysis = await sarvam.analyze_customer_message(payload.get("message", ""))
        return {"success": True, "analysis": analysis}

    # ------------------------------------------------------------------
    # WF2 — Transaction Investigation
    # ------------------------------------------------------------------

    async def _run_investigation(
        self, session: Session, *, customer_id: str, intake: dict[str, Any]
    ) -> dict[str, Any] | None:
        result = await self.n8n_run(
            "investigation",
            {
                "mission_id": self.mission_id,
                "customer_id": customer_id,
                "transaction_id": (self.mission(session).inputs or {}).get("transaction_id"),
                "amount_hint": intake.get("amount_mentioned"),
            },
            self._wf_investigation,
        )
        if not result.success:
            self.needs_attention(
                session, f"Investigation workflow failed: {result.error}"
            )
            return None

        data = result.data
        customer = data.get("customer")
        transaction = data.get("transaction")
        merchant = data.get("merchant")
        policy = data.get("policy")
        history = data.get("history", {})
        eligibility = data.get("eligibility", {})

        if not customer:
            self.fail_mission(session, "Customer record not found in the demo dataset.")
            return None

        self.emit(
            session,
            "CUSTOMER_IDENTIFIED",
            f"Customer identified: {customer['name']} ({customer['id']})",
            meta={"customer": customer},
        )
        await self.beat(0.6)

        if not transaction:
            self.emit(
                session,
                "SYSTEM_WARNING",
                "No disputed transaction found for this customer.",
                level="warn",
            )
            self.fail_mission(
                session, "No disputed transaction found for this customer."
            )
            return None

        self.emit(
            session,
            "TRANSACTION_FOUND",
            f"Transaction {transaction['id']} found — {inr(transaction['amount'])} "
            f"{transaction['payment_method']}, status {transaction['status'].replace('_', ' ')}",
            meta={"transaction": transaction},
        )
        await self.beat(0.6)

        self.emit(
            session,
            "MERCHANT_CHECKED",
            f"Merchant {merchant['name']} — settlement "
            f"{transaction['settlement_status'].replace('_', ' ')}",
            level="warn" if transaction["settlement_status"] != "settled" else "ok",
            meta={"merchant": merchant},
        )
        await self.beat(0.6)

        # Memory / Cognee recall.
        memory = await cognee.recall(
            scope="customer",
            subject_id=customer["id"],
            query=f"support history for {customer['name']}",
            local_context=self._local_memory(customer, history),
        )
        self.emit(
            session,
            "MEMORY_RETRIEVED",
            f"Context memory: {len(memory['items'])} items ({memory['detail']})",
            meta={"source": memory["source"], "detail": memory["detail"]},
        )
        await self.beat(0.6)

        self.emit(
            session,
            "POLICY_RETRIEVED",
            f"Policy {policy['id']} retrieved — {policy['title']}",
            meta={"policy": policy, "eligibility": eligibility},
        )
        await self.beat(0.6)

        # Open a support case for the issue (WRITE permission).
        case = paytm.create_case(
            session,
            customer_id=customer["id"],
            transaction_id=transaction["id"],
            issue=(self.mission(session).inputs or {}).get("message", "")[:400],
            sentiment=intake.get("sentiment", "neutral"),
            mission_id=self.mission_id,
        )
        self.emit(
            session,
            "CASE_CREATED",
            f"Support case {case['case_id']} opened",
            meta=case,
        )

        evidence = {
            "customer": customer,
            "transaction": transaction,
            "merchant": merchant,
            "policy": policy,
            "history": history,
            "eligibility": eligibility,
            "memory": memory,
            "case_id": case["case_id"],
        }

        context = self._build_context(intake, evidence)
        self.advance(
            session,
            stage="INVESTIGATING",
            progress=PROGRESS["INVESTIGATING"],
            context=context,
        )
        self.emit(
            session,
            "CONTEXT_LOADED",
            "Context loaded: customer, transaction, merchant, policy, history",
        )
        return evidence

    async def _wf_investigation(self, payload: dict[str, Any]) -> dict[str, Any]:
        with_session = self._session
        customer_id = payload.get("customer_id") or ""
        customer = paytm.get_customer(with_session, customer_id)
        if not customer:
            return {"success": False, "error": "CUSTOMER_NOT_FOUND"}

        transaction = None
        if payload.get("transaction_id"):
            transaction = paytm.get_transaction(with_session, payload["transaction_id"])
        if transaction is None:
            transaction = paytm.find_disputed_transaction(
                with_session, customer_id, payload.get("amount_hint")
            )
        if transaction is None:
            return {"success": True, "customer": customer, "transaction": None}

        merchant = paytm.get_merchant(with_session, transaction["merchant_id"])
        history = paytm.get_customer_history(with_session, customer_id)
        eligibility = paytm.is_refund_eligible(with_session, transaction["id"])
        policy_id = (
            "POL-ESCALATION-01"
            if history.get("prior_unresolved_cases", 0) > 0
            else "POL-REFUND-01"
        )
        policy = paytm.get_policy(with_session, policy_id)

        return {
            "success": True,
            "customer": customer,
            "transaction": transaction,
            "merchant": merchant,
            "history": history,
            "eligibility": eligibility,
            "policy": policy,
        }

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    async def _generate_decision(
        self, session: Session, intake: dict[str, Any], evidence: dict[str, Any]
    ) -> dict[str, Any] | None:
        transaction = evidence["transaction"]
        eligibility = evidence["eligibility"]

        base = self._rule_based_decision(intake, evidence)

        if llm.configured:
            try:
                enriched = await self._llm_decision(intake, evidence, base)
                base.update(enriched)
                base["source"] = f"llm:{llm.label}"
            except LLMUnavailable as exc:
                # An LLM was configured and could not be reached. Per the error
                # policy the mission pauses rather than silently degrading.
                log.warning("LLM unavailable: %s", exc)
                self.emit(
                    session,
                    "SYSTEM_WARNING",
                    f"Agent reasoning unavailable ({exc}). Mission paused.",
                    level="error",
                )
                update_mission(
                    session,
                    self.mission(session),
                    status="paused",
                    error=f"Agent reasoning unavailable: {exc}",
                )
                return None
        else:
            base["source"] = "deterministic_reasoner"

        # The amount is always the ledger amount, whatever the model said.
        base["amount"] = transaction["amount"] if base["action_type"] == "refund" else 0.0
        if base["action_type"] not in ALLOWED_ACTIONS:
            base["action_type"] = "escalate_to_specialist"

        base["title"] = (
            f"Refund {inr(base['amount'])}"
            if base["action_type"] == "refund"
            else "Escalate to a human specialist"
        )
        base["eligibility"] = eligibility

        self.emit(
            session,
            "DECISION_GENERATED",
            f"Decision: {base['title']}",
            meta={
                "action_type": base["action_type"],
                "amount": base["amount"],
                "source": base["source"],
            },
        )
        return base

    def _rule_based_decision(
        self, intake: dict[str, Any], evidence: dict[str, Any]
    ) -> dict[str, Any]:
        customer = evidence["customer"]
        transaction = evidence["transaction"]
        merchant = evidence["merchant"]
        eligibility = evidence["eligibility"]
        history = evidence["history"]

        items: list[str] = [
            f"Customer debit confirmed on {transaction['id']} "
            f"({inr(transaction['amount'])}, {transaction['payment_method']})",
            f"Merchant settlement to {merchant['name']} is "
            f"{transaction['settlement_status'].replace('_', ' ')}",
        ]
        if eligibility.get("within_window"):
            items.append(
                f"Transaction is inside the {eligibility.get('window_days', 7)}-day "
                f"refund window under {evidence['policy']['id']}"
            )
        prior = history.get("prior_unresolved_cases", 0)
        if prior:
            items.append(
                f"{prior} prior unresolved case(s) on record for this customer"
            )
        if intake.get("sentiment") == "strongly_negative":
            items.append("Conversation sentiment classified as strongly negative")

        if eligibility.get("eligible"):
            action_type = "refund"
            reason = (
                f"{inr(transaction['amount'])} was debited from {customer['name']} but "
                f"settlement to {merchant['name']} did not complete. "
                f"{evidence['policy']['id']} makes the debited amount refundable to source."
            )
        else:
            action_type = "escalate_to_specialist"
            reason = (
                f"{transaction['id']} does not satisfy the refund policy conditions "
                f"({eligibility.get('reason', 'ineligible')}), so a human specialist "
                "should take the case."
            )

        return {
            "action_type": action_type,
            "reason": reason,
            "evidence": items,
            "recommendation": "APPROVE",
            "confidence": 0.9 if eligibility.get("eligible") else 0.6,
        }

    async def _llm_decision(
        self,
        intake: dict[str, Any],
        evidence: dict[str, Any],
        base: dict[str, Any],
    ) -> dict[str, Any]:
        system = (
            "You are Resolve, a customer-resolution teammate inside a payments "
            "operations system. You propose one action from a fixed catalogue and "
            "explain it from the evidence you are given. You never decide whether "
            "you are permitted to execute it — a separate policy engine does that. "
            "Never invent amounts, transaction ids or policy rules. "
            "Reply with a single JSON object and no other text."
        )
        user = (
            "Evidence:\n"
            f"- Customer: {evidence['customer']['name']} "
            f"(language {evidence['customer']['language']}, "
            f"segment {evidence['customer']['segment']})\n"
            f"- Transaction: {evidence['transaction']['id']} "
            f"{inr(evidence['transaction']['amount'])} "
            f"{evidence['transaction']['payment_method']}, "
            f"status {evidence['transaction']['status']}, "
            f"settlement {evidence['transaction']['settlement_status']}\n"
            f"- Merchant: {evidence['merchant']['name']}\n"
            f"- Refund eligibility: {evidence['eligibility']}\n"
            f"- Prior unresolved cases: "
            f"{evidence['history'].get('prior_unresolved_cases', 0)}\n"
            f"- Policy: {evidence['policy']['id']} — {evidence['policy']['summary']}\n"
            f"- Customer message intent: {intake.get('intent')}, "
            f"sentiment: {intake.get('sentiment')}\n\n"
            'Respond as {"action_type": one of ["refund","escalate_to_specialist"], '
            '"reason": one or two sentences, '
            '"evidence": array of 3-5 short factual bullet strings, '
            '"customer_message": a short English message to the customer, '
            '"recommendation": "APPROVE" or "REVIEW"}'
        )
        parsed = await llm.complete_json(
            system=system,
            user=user,
            required_keys=("action_type", "reason"),
        )

        out: dict[str, Any] = {}
        if parsed.get("action_type") in ALLOWED_ACTIONS:
            out["action_type"] = parsed["action_type"]
        if isinstance(parsed.get("reason"), str) and parsed["reason"].strip():
            out["reason"] = parsed["reason"].strip()[:400]
        if isinstance(parsed.get("evidence"), list):
            bullets = [str(x)[:180] for x in parsed["evidence"] if str(x).strip()][:6]
            if bullets:
                out["evidence"] = bullets
        if isinstance(parsed.get("customer_message"), str):
            out["customer_message"] = parsed["customer_message"].strip()[:400]
        if parsed.get("recommendation") in ("APPROVE", "REVIEW"):
            out["recommendation"] = parsed["recommendation"]
        return out

    # ------------------------------------------------------------------
    # Risk routing
    # ------------------------------------------------------------------

    async def _route_decision(
        self,
        session: Session,
        intake: dict[str, Any],
        evidence: dict[str, Any],
        decision: dict[str, Any],
    ) -> None:
        transaction = evidence["transaction"]
        customer = evidence["customer"]

        proposal = ActionProposal(
            action_type=decision["action_type"],
            description=decision["title"],
            subject=(
                f"{customer['name']} · {transaction['id']} · "
                f"{inr(transaction['amount'])}"
            ),
            money_amount=decision["amount"],
            affects_account=False,
            irreversible=False,
            sentiment=intake.get("sentiment", "neutral"),
            customer_facing=True,
            evidence=decision["evidence"],
            impact=(
                f"{inr(decision['amount'])} is refunded to {customer['name']}'s source "
                f"account, the refund is verified against the ledger and the customer "
                f"is notified in {'Hindi' if customer['language'] == 'hi' else 'English'}."
                if decision["action_type"] == "refund"
                else "The case is assigned to a human specialist and the customer is notified."
            ),
            ai_recommendation=decision.get("recommendation", "APPROVE"),
            payload={
                "transaction_id": transaction["id"],
                "customer_id": customer["id"],
                "amount": decision["amount"],
                "case_id": evidence["case_id"],
            },
        )

        action, risk = self.propose(session, proposal)

        decision_card = {
            "title": decision["title"],
            "action_type": decision["action_type"],
            "amount": decision["amount"],
            "reason": decision["reason"],
            "evidence": decision["evidence"],
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
                else "Executing autonomously."
            ),
            "source": decision["source"],
            "action_id": action.id,
        }
        self.advance(session, stage="RISK_CHECK", progress=PROGRESS["RISK_CHECK"],
                     decision=decision_card)
        await self.beat()

        if risk.requires_approval:
            approval = self.request_approval(session, action, proposal, risk)
            self.advance(
                session,
                stage="WAITING_APPROVAL",
                progress=PROGRESS["WAITING_APPROVAL"],
                status="waiting_approval",
                summary={
                    "headline": f"{decision['title']} — waiting for human approval",
                    "approval_id": approval.id,
                },
            )
            return

        await self._execute_resolution(session, action, evidence, decision, approved_by=None)

    # ------------------------------------------------------------------
    # WF3 — Resolution execution
    # ------------------------------------------------------------------

    async def _execute_resolution(
        self,
        session: Session,
        action,
        evidence: dict[str, Any],
        decision: dict[str, Any],
        *,
        approved_by: str | None,
    ) -> None:
        customer = evidence["customer"]
        transaction = evidence["transaction"]

        self.advance(
            session, stage="EXECUTING", progress=PROGRESS["EXECUTING"], status="running"
        )

        message = await self._compose_customer_message(decision, evidence)

        result = await self.execute(
            session,
            action,
            workflow="resolution",
            payload={
                "mission_id": self.mission_id,
                "agent": self.agent,
                "action": decision["action_type"],
                "action_id": action.id,
                "approval_id": action.approval_id,
                "transaction_id": transaction["id"],
                "customer_id": customer["id"],
                "case_id": evidence["case_id"],
                "amount": decision["amount"],
                "message": message["text"],
                "channel": "sms",
            },
            local_handler=self._wf_resolution,
        )

        if not result.success:
            self.needs_attention(
                session,
                result.error or "The action could not be completed by the execution layer.",
            )
            return

        await self.beat(0.7)

        # Verification — a genuine ledger read-back, reported as-is.
        self.advance(session, stage="VERIFYING", progress=PROGRESS["VERIFYING"])
        verification = result.data.get("verification", {})
        if decision["action_type"] == "refund" and not verification.get("verified"):
            self.emit(
                session,
                "SYSTEM_WARNING",
                f"Refund verification failed: {verification.get('reason', 'unknown')}",
                level="error",
            )
            self.needs_attention(session, "Refund could not be verified against the ledger.")
            return

        if decision["action_type"] == "refund":
            self.emit(
                session,
                "ACTION_VERIFIED",
                f"Refund verified — {transaction['id']} is now "
                f"'{verification.get('status')}' in the ledger",
                meta=verification,
            )
        else:
            self.emit(
                session,
                "ACTION_VERIFIED",
                f"Case {evidence['case_id']} confirmed assigned to a specialist",
                meta=result.data.get("assignment", {}),
            )
        await self.beat(0.7)

        notification = result.data.get("notification", {})
        self.emit(
            session,
            "MESSAGE_SENT",
            f"Customer notified on {notification.get('channel', 'sms')} "
            f"({message['language_label']}, {message['source']})",
            meta={"notification": notification, "text": message["text"]},
        )
        await self.beat(0.6)

        if approved_by:
            outcome_result = "resolved_with_approval"
            label = f"Resolved after human approval by {approved_by}"
        elif decision["action_type"] == "refund":
            outcome_result = "resolved_autonomously"
            label = "Resolved autonomously"
        else:
            outcome_result = "handled_by_human"
            label = "Assigned to a human specialist"

        # Re-read the ledger so the context panel shows post-execution state
        # rather than the snapshot taken during investigation.
        mission = self.mission(session)
        stored_context = mission.context or {}
        fresh = paytm.get_transaction(session, transaction["id"])
        if fresh:
            evidence = {**evidence, "transaction": fresh}
        refreshed_context = self._build_context(
            stored_context.get("intake", {}), evidence
        )

        # The decision card becomes the record of what was decided *and* what
        # happened to it, instead of freezing on "approval required".
        decision_card = dict(mission.decision or {})
        decision_card["resolved"] = True
        decision_card["next"] = (
            f"Approved by {approved_by} · executed and verified."
            if approved_by
            else "Executed autonomously and verified."
        )

        summary = {
            "headline": (
                f"{inr(decision['amount'])} refunded and verified"
                if decision["action_type"] == "refund"
                else "Case assigned to a human specialist"
            ),
            "lines": [
                f"{decision['title']} executed via {result.workflow_code}"
                f" ({result.executed_via})",
                "Refund verified against the transaction ledger"
                if decision["action_type"] == "refund"
                else "Specialist assignment confirmed",
                f"Customer notified in {message['language_label']}",
            ],
            "customer_message": message["text"],
            "case_id": evidence["case_id"],
            "amount": decision["amount"],
            "executed_via": result.executed_via,
            "workflow": result.workflow_code,
        }

        self.emit(session, "MISSION_COMPLETED", f"Mission complete — {label}")
        self.advance(
            session,
            stage="RESOLVED",
            progress=PROGRESS["RESOLVED"],
            status="completed",
            result=outcome_result,
            result_label=label,
            summary=summary,
            context=refreshed_context,
            decision=decision_card,
        )

    async def _wf_resolution(self, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._session
        out: dict[str, Any] = {"success": True, "action_id": payload.get("action_id")}

        if payload.get("action") == "refund":
            refund = paytm.execute_refund(
                session,
                payload["transaction_id"],
                float(payload["amount"]),
                reference=f"PULSE-{payload['mission_id']}-{payload['action_id']}",
            )
            out["refund"] = refund
            if not refund.get("success"):
                return {
                    "success": False,
                    "error": f"Refund rejected by the payments boundary: {refund.get('error')}",
                    "refund": refund,
                }
            out["verification"] = paytm.verify_refund(session, payload["transaction_id"])
            paytm.close_case(
                session,
                payload["case_id"],
                resolution=f"Refunded {inr(float(payload['amount']))} to source.",
            )
        else:
            out["assignment"] = paytm.reassign_case(
                session, payload["case_id"], assignee="human_specialist"
            )
            out["verification"] = {"verified": True, "reason": "Case reassigned"}

        out["notification"] = paytm.send_notification(
            session,
            payload["customer_id"],
            payload.get("channel", "sms"),
            payload.get("message", ""),
        )
        out["status"] = "executed"
        return out

    # ------------------------------------------------------------------
    # Approval continuations
    # ------------------------------------------------------------------

    async def continue_after_approval(
        self, session: Session, approval: Approval, reviewer: str
    ) -> None:
        self.bind(session)
        mission = self.mission(session)
        evidence = self._evidence_from_context(session, mission.context or {})
        decision = dict(mission.decision or {})
        decision.setdefault("action_type", "refund")
        decision.setdefault("title", approval.title)
        decision.setdefault("amount", (evidence["transaction"] or {}).get("amount", 0.0))
        decision.setdefault("reason", approval.reason)
        decision.setdefault("evidence", approval.evidence or [])
        decision.setdefault("source", "deterministic_reasoner")

        action = session.get(Action, approval.action_id)
        if action is None:
            self.fail_mission(session, "Approved action no longer exists.")
            return

        action.status = "proposed"
        session.add(action)
        session.commit()

        update_mission(session, mission, human_involved=True)
        await self.beat(0.5)
        await self._execute_resolution(
            session, action, evidence, decision, approved_by=reviewer
        )

    async def continue_after_rejection(
        self, session: Session, approval: Approval, reviewer: str
    ) -> None:
        """Rejected actions take the alternative path, not a dead end."""
        self.bind(session)
        mission = self.mission(session)
        evidence = self._evidence_from_context(session, mission.context or {})
        customer = evidence["customer"]
        transaction = evidence["transaction"]
        case_id = evidence.get("case_id")

        update_mission(
            session,
            mission,
            status="running",
            stage="EXECUTING",
            progress=PROGRESS["EXECUTING"],
            human_involved=True,
        )
        await self.beat(0.5)

        if case_id:
            assignment = paytm.reassign_case(session, case_id, assignee="human_specialist")
            self.emit(
                session,
                "ACTION_VERIFIED",
                f"Case {case_id} reassigned to a human specialist",
                meta=assignment,
            )
        await self.beat(0.5)

        text = CUSTOMER_TEMPLATES[
            "escalate_hi" if customer.get("language") == "hi" else "escalate_en"
        ].format(
            name=customer.get("name", ""),
            tx=(transaction or {}).get("id", ""),
            case=case_id or "",
        )
        notification = paytm.send_notification(session, customer["id"], "sms", text)
        self.emit(
            session,
            "MESSAGE_SENT",
            "Customer notified that a specialist will follow up",
            meta={"notification": notification, "text": text},
        )

        label = f"Rejected by {reviewer} — handed to a human specialist"
        decision_card = dict(self.mission(session).decision or {})
        decision_card["resolved"] = True
        decision_card["next"] = f"Rejected by {reviewer} · handed to a specialist."

        self.emit(session, "MISSION_COMPLETED", f"Mission closed — {label}")
        self.advance(
            session,
            stage="RESOLVED",
            progress=100,
            status="completed",
            result="rejected_by_human",
            result_label=label,
            decision=decision_card,
            summary={
                "headline": "Action rejected — handed to a human specialist",
                "lines": [
                    f"{approval.title} was rejected by {reviewer}",
                    f"Case {case_id} reassigned to a human specialist",
                    "Customer notified",
                ],
                "customer_message": text,
                "case_id": case_id,
            },
        )
        publish_approvals_changed()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _compose_customer_message(
        self, decision: dict[str, Any], evidence: dict[str, Any]
    ) -> dict[str, Any]:
        customer = evidence["customer"]
        transaction = evidence["transaction"]
        language = customer.get("language", "en")
        language_label = "Hindi" if language == "hi" else "English"

        if decision["action_type"] == "refund":
            english = decision.get("customer_message") or CUSTOMER_TEMPLATES[
                "refund_en"
            ].format(
                name=customer["name"],
                tx=transaction["id"],
                amount=inr(decision["amount"]),
            )
            hindi_template = CUSTOMER_TEMPLATES["refund_hi"].format(
                name=customer["name"],
                tx=transaction["id"],
                amount=inr(decision["amount"]),
            )
        else:
            english = decision.get("customer_message") or CUSTOMER_TEMPLATES[
                "escalate_en"
            ].format(
                name=customer["name"],
                tx=transaction["id"],
                case=evidence.get("case_id", ""),
            )
            hindi_template = CUSTOMER_TEMPLATES["escalate_hi"].format(
                name=customer["name"],
                tx=transaction["id"],
                case=evidence.get("case_id", ""),
            )

        if language == "en":
            return {"text": english, "language_label": "English", "source": "template"}

        if sarvam.configured:
            composed = await sarvam.compose_in_language(english, f"{language}-IN")
            if composed.get("translated"):
                return {
                    "text": composed["text"],
                    "language_label": language_label,
                    "source": "Sarvam",
                }
        return {
            "text": hindi_template,
            "language_label": language_label,
            "source": "template",
        }

    @staticmethod
    def _local_memory(customer: dict[str, Any], history: dict[str, Any]) -> list[dict]:
        items = [
            {
                "label": "Customer since",
                "value": customer.get("joined_on", "—"),
                "kind": "profile",
            },
            {
                "label": "Transactions on record",
                "value": str(history.get("transaction_count", 0)),
                "kind": "history",
            },
            {
                "label": "Previous support cases",
                "value": str(history.get("case_count", 0)),
                "kind": "history",
            },
        ]
        if history.get("prior_unresolved_cases"):
            items.append(
                {
                    "label": "Unresolved cases",
                    "value": f"{history['prior_unresolved_cases']} open before this mission",
                    "kind": "signal",
                }
            )
        return items

    def _build_context(
        self, intake: dict[str, Any], evidence: dict[str, Any]
    ) -> dict[str, Any]:
        customer = evidence["customer"]
        transaction = evidence["transaction"]
        merchant = evidence["merchant"]
        policy = evidence["policy"]

        return {
            "kind": "resolve",
            "customer": customer,
            "transaction": transaction,
            "merchant": merchant,
            "policy": policy,
            "history": evidence["history"],
            "eligibility": evidence["eligibility"],
            "intake": intake,
            "memory": {
                "source": evidence["memory"]["source"],
                "detail": evidence["memory"]["detail"],
                "items": evidence["memory"]["items"],
            },
            "case_id": evidence["case_id"],
            "panels": [
                {
                    "title": "Customer",
                    "rows": [
                        {"label": "Name", "value": customer["name"]},
                        {"label": "ID", "value": customer["id"]},
                        {
                            "label": "Language",
                            "value": intake.get("language_name", customer["language"]),
                        },
                        {"label": "Segment", "value": customer["segment"].title()},
                    ],
                },
                {
                    "title": "Transaction",
                    "rows": [
                        {"label": "Reference", "value": transaction["id"]},
                        {"label": "Amount", "value": inr(transaction["amount"])},
                        {"label": "Method", "value": transaction["payment_method"]},
                        {
                            "label": "Status",
                            "value": transaction["status"].replace("_", " ").title(),
                            "tone": "warn"
                            if transaction["status"] != "success"
                            else "ok",
                        },
                    ],
                },
                {
                    "title": "Merchant",
                    "rows": [
                        {"label": "Name", "value": merchant["name"]},
                        {"label": "Location", "value": merchant["location"]},
                        {
                            "label": "Settlement",
                            "value": transaction["settlement_status"]
                            .replace("_", " ")
                            .title(),
                            "tone": "warn"
                            if transaction["settlement_status"] != "settled"
                            else "ok",
                        },
                    ],
                },
                {
                    "title": "Case",
                    "rows": [
                        {
                            "label": "Intent",
                            "value": intake.get("intent_label", intake.get("intent", "—")),
                        },
                        {
                            "label": "Sentiment",
                            "value": intake.get("sentiment", "neutral")
                            .replace("_", " ")
                            .title(),
                            "tone": "warn"
                            if intake.get("sentiment") == "strongly_negative"
                            else "ok",
                        },
                        {"label": "Policy", "value": f"{policy['id']} · {policy['title']}"},
                        {
                            "label": "Prior cases",
                            "value": str(
                                evidence["history"].get("prior_unresolved_cases", 0)
                            ),
                        },
                    ],
                },
            ],
        }

    def _evidence_from_context(
        self, session: Session, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Rebuild the evidence bundle when resuming after human review."""
        transaction_id = (context.get("transaction") or {}).get("id")
        fresh_tx = (
            paytm.get_transaction(session, transaction_id) if transaction_id else None
        )
        return {
            "customer": context.get("customer") or {},
            "transaction": fresh_tx or context.get("transaction") or {},
            "merchant": context.get("merchant") or {},
            "policy": context.get("policy") or {},
            "history": context.get("history") or {},
            "eligibility": context.get("eligibility") or {},
            "memory": context.get("memory") or {"items": [], "source": "local_context"},
            "case_id": context.get("case_id"),
        }
