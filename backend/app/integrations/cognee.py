"""Cognee adapter — contextual memory for the teammates.

Memory is never a UI screen. Agents call `recall()` while loading context and the
retrieved items appear inline in the mission context panel.

When COGNEE_API_URL is configured, recall is served by Cognee. Otherwise the
adapter returns context derived from the canonical application database and
labels it `local_context` — it never pretends a memory service answered.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("pulse.cognee")


class CogneeAdapter:
    def __init__(self) -> None:
        self.api_url = settings.cognee_api_url.rstrip("/")
        self.api_key = settings.cognee_api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_url)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def recall(
        self,
        *,
        scope: str,
        subject_id: str,
        query: str,
        local_context: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Retrieve relevant memory for a subject.

        `local_context` is the database-derived context the caller already built.
        It is both the fallback and the floor: Cognee results are added on top,
        never substituted for canonical transactional state.
        """
        if not self.configured:
            return {
                "items": local_context,
                "source": "local_context",
                "detail": "Derived from the application database",
                "available": True,
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.api_url}/search",
                    headers=self._headers(),
                    json={
                        "query": query,
                        "search_type": "GRAPH_COMPLETION",
                        "datasets": [f"pulse_{scope}"],
                        "node_name": [subject_id],
                    },
                )
                resp.raise_for_status()
                payload = resp.json()

            remembered = _normalize_cognee_results(payload)
            return {
                "items": local_context + remembered,
                "source": "cognee",
                "detail": f"Cognee graph recall ({len(remembered)} items)",
                "available": True,
            }
        except Exception as exc:  # noqa: BLE001 - degrade, never break the mission
            log.warning("Cognee unavailable (%s); using database context", exc)
            return {
                "items": local_context,
                "source": "local_context",
                "detail": "Cognee unavailable — using database context",
                "available": False,
                "error": str(exc)[:160],
            }

    async def remember(
        self, *, scope: str, subject_id: str, text: str, meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Write an observation back to memory."""
        if not self.configured:
            return {"stored": False, "source": "local_context"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.api_url}/add",
                    headers=self._headers(),
                    json={
                        "data": text,
                        "dataset_name": f"pulse_{scope}",
                        "node_name": subject_id,
                        "metadata": meta or {},
                    },
                )
                resp.raise_for_status()
            return {"stored": True, "source": "cognee"}
        except Exception as exc:  # noqa: BLE001
            log.warning("Cognee write failed (%s)", exc)
            return {"stored": False, "source": "cognee", "error": str(exc)[:160]}


def _normalize_cognee_results(payload: Any) -> list[dict[str, Any]]:
    results = payload.get("results", payload) if isinstance(payload, dict) else payload
    items: list[dict[str, Any]] = []
    if isinstance(results, list):
        for entry in results[:5]:
            text = entry if isinstance(entry, str) else str(
                entry.get("text") or entry.get("content") or entry
            )
            items.append({"label": "Memory", "value": text[:280], "kind": "cognee"})
    return items


cognee = CogneeAdapter()
