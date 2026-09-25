"""LLM adapter — the reasoning layer.

The model writes the *narrative*: which action fits the evidence, why, and how to
phrase the customer or merchant message. It never writes the *numbers* and it
never decides whether it is allowed to act. Amounts come from the ledger and
permission comes from the deterministic policy engine — the agents enforce both
after this adapter returns.

With no LLM configured the same structured decisions are produced by a rule-based
reasoner, so the full mission still runs end to end offline.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("pulse.llm")

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-4.1-mini",
    "openai_compatible": "",
    "sarvam": "sarvam-m",
}


class LLMUnavailable(RuntimeError):
    """Raised when the configured model cannot be reached."""


class LLMAdapter:
    def __init__(self) -> None:
        self.provider = (settings.llm_provider or "").strip().lower()
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model or DEFAULT_MODELS.get(self.provider, "")
        self.base_url = settings.llm_base_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.provider and self.api_key)

    @property
    def label(self) -> str:
        if not self.configured:
            return "Deterministic policy reasoner"
        return f"{self.provider}:{self.model}"

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        required_keys: tuple[str, ...],
        max_tokens: int = 700,
    ) -> dict[str, Any]:
        """Ask the model for a JSON object and validate its shape."""
        if not self.configured:
            raise LLMUnavailable("No LLM provider configured")

        raw = await self._call(system=system, user=user, max_tokens=max_tokens)
        parsed = _first_json_object(raw)
        if parsed is None:
            raise LLMUnavailable("Model did not return a JSON object")
        missing = [k for k in required_keys if k not in parsed]
        if missing:
            raise LLMUnavailable(f"Model response missing keys: {missing}")
        return parsed

    async def _call(self, *, system: str, user: str, max_tokens: int) -> str:
        try:
            if self.provider == "anthropic":
                return await self._call_anthropic(system, user, max_tokens)
            return await self._call_openai_style(system, user, max_tokens)
        except LLMUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailable(str(exc)[:200]) from exc

    async def _call_anthropic(self, system: str, user: str, max_tokens: int) -> str:
        base = self.base_url or "https://api.anthropic.com"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        blocks = data.get("content") or []
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    async def _call_openai_style(self, system: str, user: str, max_tokens: int) -> str:
        if self.provider == "sarvam":
            base = self.base_url or f"{settings.sarvam_base_url.rstrip('/')}/v1"
            headers = {
                "api-subscription-key": self.api_key,
                "Content-Type": "application/json",
            }
        else:
            base = self.base_url or "https://api.openai.com/v1"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        if not self.model:
            raise LLMUnavailable("LLM_MODEL is not set for this provider")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"] or ""

    async def health(self) -> dict[str, Any]:
        if not self.configured:
            return {"available": False, "reason": "not_configured", "label": self.label}
        try:
            await asyncio.wait_for(
                self._call(system="Reply with OK.", user="ping", max_tokens=8),
                timeout=20,
            )
            return {"available": True, "label": self.label}
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "reason": str(exc)[:160], "label": self.label}


def _first_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        for idx in range(start, len(text)):
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start : idx + 1])
                    except json.JSONDecodeError:
                        break
                    return value if isinstance(value, dict) else None
        start = text.find("{", start + 1)
    return None


llm = LLMAdapter()
