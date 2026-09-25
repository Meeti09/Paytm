"""Shared agent machinery.

Both teammates are explicit state machines, not open-ended loops. This base
class owns the parts that must behave identically for every agent:

    propose an action -> policy engine judges it -> execute via n8n, or stop and
    ask a human -> verify -> record the outcome

The policy check happens here, once, for every action. An agent cannot execute
anything without going through `propose()`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.permissions import action_label, authorize_action
from app.config import settings
from app.integrations.n8n import WorkflowResult, n8n
from app.models.models import Action, Approval, Mission, utcnow
from app.policy.risk import ActionProposal, RiskDecision, evaluate_action
from app.services.event_service import (
    publish_approvals_changed,
    record_event,
)
from app.services.mission_service import (
    next_sequence_id,
    serialize_approval,
    update_mission,
)

log = logging.getLogger("pulse.agent")


class MissionAborted(Exception):
    """Raised when a human takes over or the mission is stopped mid-run."""


class BaseAgent:
    agent: str = "base"

    def __init__(self, mission_id: str) -> None:
        self.mission_id = mission_id
        # Bound for the duration of a run so local workflow handlers — which
        # receive only a JSON payload, exactly like an n8n webhook would — can
        # still reach the database.
        self._session: Session | None = None

    def bind(self, session: Session) -> None:
        self._session = session

    # ---- plumbing ------------------------------------------------------

    async def n8n_run(
        self, workflow: str, payload: dict[str, Any], local_handler
    ) -> WorkflowResult:
        """Run a named workflow through the execution layer."""
        return await n8n.run(workflow, payload, local=local_handler)

    def mission(self, session: Session) -> Mission:
        mission = session.get(Mission, self.mission_id)
        if mission is None:
            raise MissionAborted(f"Mission {self.mission_id} no longer exists")
        return mission

    async def beat(self, factor: float = 1.0) -> None:
        """Pace the mission so the live timeline is readable on stage."""
        delay = settings.step_delay * factor
        if delay > 0:
            await asyncio.sleep(delay)

    def guard(self, session: Session) -> Mission:
        """Stop immediately if a human has taken the mission over."""
        mission = self.mission(session)
        if mission.status in ("human_takeover", "paused"):
            raise MissionAborted(f"Mission {self.mission_id} is {mission.status}")
        return mission

    def emit(
        self,
        session: Session,
        event_type: str,
        message: str,
        *,
        level: str = "ok",
        meta: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> None:
        record_event(
            session,
            self.mission_id,
            event_type,
            message,
            actor=actor or self.agent,
            level=level,
            meta=meta or {},
        )

    def advance(
        self,
        session: Session,
        *,
        stage: str,
        progress: int,
        status: str | None = None,
        **fields: Any,
    ) -> Mission:
        mission = self.mission(session)
        payload: dict[str, Any] = {"stage": stage, "progress": progress, **fields}
        if status:
            payload["status"] = status
        return update_mission(session, mission, **payload)

    # ---- the autonomy boundary ------------------------------------------

    def propose(
        self, session: Session, proposal: ActionProposal
    ) -> tuple[Action, RiskDecision]:
        """Record a proposed action and run it through the policy engine.

        The proposal's `authorized` flag is recomputed here from the agent's
        declared permissions — an agent (or a model behind it) cannot mark its
        own action as authorized.
        """
        authorized, note = authorize_action(self.agent, proposal.action_type)
        proposal.authorized = authorized
        if not authorized:
            proposal.permission_note = note

        risk = evaluate_action(proposal)

        action = Action(
            id=next_sequence_id(session, Action, "ACT"),
            mission_id=self.mission_id,
            action_type=proposal.action_type,
            description=proposal.description,
            risk_level=risk.risk_level,
            requires_approval=risk.requires_approval,
            status="pending_approval" if risk.requires_approval else "proposed",
            payload=proposal.payload,
        )
        session.add(action)
        session.commit()
        session.refresh(action)

        self.emit(
            session,
            "ACTION_PROPOSED",
            f"Action proposed: {proposal.description}",
            meta={
                "action_id": action.id,
                "action_type": proposal.action_type,
                "label": action_label(proposal.action_type),
            },
        )
        self.emit(
            session,
            "RISK_EVALUATED",
            (
                f"Policy check: {risk.primary_rule} — approval required"
                if risk.requires_approval
                else f"Policy check: within autonomous limits ({risk.risk_level} risk)"
            ),
            level="warn" if risk.requires_approval else "ok",
            meta={"action_id": action.id, **risk.as_dict()},
        )
        return action, risk

    def request_approval(
        self,
        session: Session,
        action: Action,
        proposal: ActionProposal,
        risk: RiskDecision,
    ) -> Approval:
        """Stop the mission and hand the decision to a human."""
        approval = Approval(
            id=next_sequence_id(session, Approval, "APR"),
            mission_id=self.mission_id,
            action_id=action.id,
            agent=self.agent,
            title=proposal.description,
            subject=proposal.subject,
            reason=risk.reason,
            policy_rule=risk.primary_rule,
            policy_detail=risk.policy_detail,
            risk_level=risk.risk_level,
            evidence=proposal.evidence,
            triggered_rules=[
                {"rule": t.rule, "detail": t.detail, "risk": t.risk}
                for t in risk.triggered
            ],
            ai_recommendation=proposal.ai_recommendation,
            impact=proposal.impact,
            status="pending",
        )
        session.add(approval)
        action.approval_id = approval.id
        action.status = "pending_approval"
        session.add(action)
        session.commit()
        session.refresh(approval)

        self.emit(
            session,
            "APPROVAL_REQUESTED",
            f"Human approval requested — {risk.reason}",
            level="warn",
            meta={
                "approval_id": approval.id,
                "action_id": action.id,
                "policy_rule": risk.primary_rule,
                "risk_level": risk.risk_level,
            },
        )
        publish_approvals_changed()
        return approval

    async def execute(
        self,
        session: Session,
        action: Action,
        *,
        workflow: str,
        payload: dict[str, Any],
        local_handler,
    ) -> WorkflowResult:
        """Hand a cleared action to the execution layer."""
        action.status = "executing"
        session.add(action)
        session.commit()

        result = await n8n.run(workflow, payload, local=local_handler)

        action.executed_via = result.executed_via
        action.result = result.as_dict()
        action.status = "executed" if result.success else "failed"
        action.completed_at = utcnow()
        session.add(action)
        session.commit()

        if result.success:
            self.emit(
                session,
                "ACTION_EXECUTED",
                f"{action.description} executed via {result.workflow_code} "
                f"({'n8n' if result.executed_via == 'n8n' else 'local workflow runner'})",
                meta={
                    "action_id": action.id,
                    "workflow": result.workflow,
                    "workflow_code": result.workflow_code,
                    "executed_via": result.executed_via,
                    "data": result.data,
                },
            )
        else:
            self.emit(
                session,
                "ACTION_FAILED",
                f"Execution failed in {result.workflow_code}: {result.error}",
                level="error",
                meta={
                    "action_id": action.id,
                    "workflow": result.workflow,
                    "error": result.error,
                },
            )
        return result

    def fail_mission(self, session: Session, reason: str, *, stage: str = "FAILED") -> None:
        self.emit(session, "MISSION_FAILED", reason, level="error")
        self.advance(
            session,
            stage=stage,
            progress=100,
            status="failed",
            result="failed",
            result_label=reason[:160],
            error=reason,
        )

    def needs_attention(self, session: Session, reason: str) -> None:
        self.emit(session, "SYSTEM_WARNING", reason, level="error")
        mission = self.mission(session)
        update_mission(
            session,
            mission,
            status="needs_attention",
            error=reason,
        )

    # ---- continuations driven by the orchestrator -------------------------

    async def run(self, session: Session) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    async def retry(self, session: Session) -> None:
        """Re-run a mission that stopped on a recoverable error."""
        await self.run(session)

    async def continue_after_approval(
        self, session: Session, approval: Approval, reviewer: str
    ) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    async def continue_after_rejection(
        self, session: Session, approval: Approval, reviewer: str
    ) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    async def _continue_approved(
        self, session: Session, approval_id: str, reviewer: str
    ) -> None:
        approval = session.get(Approval, approval_id)
        if approval is None:
            return
        await self.continue_after_approval(session, approval, reviewer)

    async def _continue_rejected(
        self, session: Session, approval_id: str, reviewer: str
    ) -> None:
        approval = session.get(Approval, approval_id)
        if approval is None:
            return
        await self.continue_after_rejection(session, approval, reviewer)

    # ---- helpers for the API --------------------------------------------

    @staticmethod
    def approval_payload(session: Session, approval: Approval) -> dict[str, Any]:
        return serialize_approval(approval)
