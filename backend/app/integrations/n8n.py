"""n8n adapter — the execution layer ("the hands of the AI").

Agents never touch external systems directly. A decision that has cleared the
policy engine is handed to a named workflow here, and the workflow performs the
side effect against the simulated Paytm boundary.

Two execution modes, one contract:

* N8N_BASE_URL set  -> the real n8n webhook runs (`n8n/workflows/*.json`).
* N8N_BASE_URL unset -> LocalWorkflowRunner executes the *same* workflow steps
  in-process, so the workflow boundary survives even without an n8n instance.

Failures are reported, never swallowed: the mission moves to NEEDS_ATTENTION and
the operator gets a retry.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("pulse.n8n")

# Logical workflow catalogue (Architecture.md §15–16).
WORKFLOWS: dict[str, dict[str, str]] = {
    "issue-intake": {"code": "WF1", "name": "Customer Issue Intake", "agent": "resolve"},
    "investigation": {"code": "WF2", "name": "Transaction Investigation", "agent": "resolve"},
    "resolution": {"code": "WF3", "name": "Resolution Execution", "agent": "resolve"},
    "lead-discovery": {"code": "WF4", "name": "Lead Discovery", "agent": "grow"},
    "outreach": {"code": "WF5", "name": "Outreach & Qualification", "agent": "grow"},
    "followup": {"code": "WF6", "name": "Follow-up & Meeting", "agent": "grow"},
}


@dataclass
class WorkflowResult:
    success: bool
    workflow: str
    workflow_code: str
    executed_via: str  # "n8n" | "local"
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "workflow": self.workflow,
            "workflow_code": self.workflow_code,
            "executed_via": self.executed_via,
            "data": self.data,
            "error": self.error,
        }


LocalHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class N8nAdapter:
    def __init__(self) -> None:
        self.base_url = settings.n8n_base_url.rstrip("/")
        self.api_key = settings.n8n_api_key
        self.prefix = settings.n8n_webhook_prefix

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    @property
    def label(self) -> str:
        return "n8n webhooks" if self.configured else "Local workflow runner"

    def webhook_url(self, workflow: str) -> str:
        return f"{self.base_url}{self.prefix}/{workflow}"

    async def run(
        self,
        workflow: str,
        payload: dict[str, Any],
        *,
        local: LocalHandler,
    ) -> WorkflowResult:
        """Run a named workflow, via n8n when available, locally otherwise."""
        meta = WORKFLOWS.get(workflow, {"code": "WF?", "name": workflow})
        code = meta["code"]

        if not self.configured:
            try:
                data = await local(payload)
                return WorkflowResult(
                    success=bool(data.get("success", True)),
                    workflow=workflow,
                    workflow_code=code,
                    executed_via="local",
                    data=data,
                    error=str(data.get("error", "")),
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("Local workflow %s failed", workflow)
                return WorkflowResult(
                    success=False,
                    workflow=workflow,
                    workflow_code=code,
                    executed_via="local",
                    error=str(exc)[:240],
                )

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.webhook_url(workflow), headers=headers, json=payload
                )
                resp.raise_for_status()
                data = resp.json()
            if isinstance(data, list) and data:
                data = data[0]
            if not isinstance(data, dict):
                data = {"result": data}
            return WorkflowResult(
                success=bool(data.get("success", True)),
                workflow=workflow,
                workflow_code=code,
                executed_via="n8n",
                data=data,
                error=str(data.get("error", "")),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("n8n workflow %s failed: %s", workflow, exc)
            return WorkflowResult(
                success=False,
                workflow=workflow,
                workflow_code=code,
                executed_via="n8n",
                error=f"n8n execution failed: {str(exc)[:200]}",
            )


n8n = N8nAdapter()
