"""Sarvam adapter — the India-native language layer.

Turns a real customer message ("₹2,000 कट गया लेकिन merchant को नहीं मिला") into a
structured intent the Resolve teammate can act on.

When SARVAM_API_KEY is set this calls the Sarvam API for language identification
and structured understanding. When it is not set — or the call fails — it falls
back to a local deterministic classifier and says so. The mission never stalls
because a language service is unavailable, and the UI always shows which path ran.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("pulse.sarvam")

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_AMOUNT = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)|([\d,]{3,})", re.I)

LANGUAGE_NAMES = {
    "hi-IN": "Hindi",
    "en-IN": "English",
    "mr-IN": "Marathi",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "bn-IN": "Bengali",
    "gu-IN": "Gujarati",
    "kn-IN": "Kannada",
}

INTENTS = {
    "payment_failed_after_debit": "Amount debited but not received by merchant",
    "payment_delayed": "Payment or settlement delayed",
    "refund_status": "Refund status enquiry",
    "merchant_onboarding_interest": "Merchant interested in Paytm onboarding",
    "general_support": "General support request",
}

# Local fallback keyword sets (Hindi + English + transliterated).
_DEBIT_MARKERS = ("कट गया", "कट गए", "debited", "debit", "कट", "पैसा गया", "paisa kat")
_NOT_RECEIVED = (
    "नहीं मिला",
    "नहीं मिले",
    "not received",
    "not credited",
    "nahi mila",
    "नहीं पहुंचा",
    "merchant को नहीं",
)
_DELAY_MARKERS = ("delay", "delayed", "देर", "pending", "अटका", "stuck", "late")
_REFUND_MARKERS = ("refund", "रिफंड", "वापस", "wapas", "पैसे वापस")
_ONBOARD_MARKERS = ("लगाने", "onboard", "qr", "paytm लगा", "machine", "soundbox")

_STRONG_NEGATIVE = (
    "तीन बार",
    "कई बार",
    "बार शिकायत",
    "अभी तक",
    "third time",
    "3rd time",
    "again and again",
    "worst",
    "pathetic",
    "terrible",
    "useless",
    "fed up",
    "शिकायत कर चुका",
    "शिकायत कर चुकी",
    "no response",
    "कोई जवाब नहीं",
)
_NEGATIVE = ("problem", "issue", "परेशान", "समस्या", "नहीं हुआ", "failed", "complaint")


def _extract_amount(text: str) -> float | None:
    for match in _AMOUNT.finditer(text):
        raw = match.group(1) or match.group(2)
        if not raw:
            continue
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if value >= 1:
            return value
    return None


def _local_language(text: str) -> tuple[str, str]:
    if _DEVANAGARI.search(text):
        latin = len(re.findall(r"[A-Za-z]", text))
        deva = len(_DEVANAGARI.findall(text))
        if latin > deva:
            return "hi-IN", "Latin"
        return "hi-IN", "Devanagari"
    return "en-IN", "Latin"


def _local_intent(text: str) -> str:
    low = text.lower()
    hit = lambda words: any(w.lower() in low for w in words)  # noqa: E731
    if hit(_ONBOARD_MARKERS):
        return "merchant_onboarding_interest"
    if hit(_DEBIT_MARKERS) and hit(_NOT_RECEIVED):
        return "payment_failed_after_debit"
    if hit(_REFUND_MARKERS):
        return "refund_status"
    if hit(_DELAY_MARKERS):
        return "payment_delayed"
    if hit(_DEBIT_MARKERS):
        return "payment_failed_after_debit"
    return "general_support"


def _local_sentiment(text: str) -> str:
    low = text.lower()
    if any(w.lower() in low for w in _STRONG_NEGATIVE):
        return "strongly_negative"
    if text.count("!") >= 2:
        return "strongly_negative"
    if any(w.lower() in low for w in _NEGATIVE):
        return "negative"
    return "neutral"


def _local_analysis(text: str) -> dict[str, Any]:
    language, script = _local_language(text)
    intent = _local_intent(text)
    return {
        "intent": intent,
        "intent_label": INTENTS.get(intent, intent),
        "language": language,
        "language_name": LANGUAGE_NAMES.get(language, language),
        "script": script,
        "sentiment": _local_sentiment(text),
        "amount_mentioned": _extract_amount(text),
        "normalized_text": text.strip(),
        "source": "fallback",
        "source_detail": "Local language + intent classifier",
    }


class SarvamAdapter:
    """Language understanding for customer and merchant messages."""

    def __init__(self) -> None:
        self.api_key = settings.sarvam_api_key
        self.base_url = settings.sarvam_base_url.rstrip("/")
        self.model = settings.sarvam_model

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def detect_language(self, text: str) -> dict[str, Any]:
        """Sarvam text language identification, with local fallback."""
        if not self.configured:
            language, script = _local_language(text)
            return {
                "language": language,
                "script": script,
                "source": "fallback",
            }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{self.base_url}/text-lid",
                    headers=self._headers(),
                    json={"input": text},
                )
                resp.raise_for_status()
                data = resp.json()
            return {
                "language": data.get("language_code") or "en-IN",
                "script": data.get("script_code") or "",
                "source": "sarvam",
            }
        except Exception as exc:  # noqa: BLE001 - degrade, never break the mission
            log.warning("Sarvam language id unavailable (%s); using fallback", exc)
            language, script = _local_language(text)
            return {
                "language": language,
                "script": script,
                "source": "fallback",
                "error": str(exc)[:160],
            }

    async def translate_to_english(self, text: str, source_language: str) -> dict[str, Any]:
        if not self.configured or source_language.startswith("en"):
            return {"text": text, "source": "fallback", "translated": False}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/translate",
                    headers=self._headers(),
                    json={
                        "input": text,
                        "source_language_code": source_language,
                        "target_language_code": "en-IN",
                        "mode": "formal",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            return {
                "text": data.get("translated_text") or text,
                "source": "sarvam",
                "translated": True,
            }
        except Exception as exc:  # noqa: BLE001
            log.warning("Sarvam translate unavailable (%s); using original text", exc)
            return {
                "text": text,
                "source": "fallback",
                "translated": False,
                "error": str(exc)[:160],
            }

    async def analyze_customer_message(self, text: str) -> dict[str, Any]:
        """Normalise a raw customer message into a structured support intent."""
        local = _local_analysis(text)
        if not self.configured:
            return local

        lang = await self.detect_language(text)
        local["language"] = lang.get("language", local["language"])
        local["language_name"] = LANGUAGE_NAMES.get(
            local["language"], local["language"]
        )
        local["script"] = lang.get("script", local["script"])

        prompt = (
            "You classify Paytm customer support messages. Respond with JSON only, "
            'using exactly these keys: {"intent": one of '
            f"{sorted(INTENTS)}, "
            '"sentiment": one of ["neutral","negative","strongly_negative"], '
            '"summary": a one-line English summary}. '
            "Do not include any other text.\n\nMessage: " + text
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=self._headers(),
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
            content = payload["choices"][0]["message"]["content"]
            parsed = _first_json_object(content)
            if parsed:
                intent = parsed.get("intent")
                if intent in INTENTS:
                    local["intent"] = intent
                    local["intent_label"] = INTENTS[intent]
                sentiment = parsed.get("sentiment")
                if sentiment in ("neutral", "negative", "strongly_negative"):
                    local["sentiment"] = sentiment
                if parsed.get("summary"):
                    local["summary"] = str(parsed["summary"])[:240]
            local["source"] = "sarvam"
            local["source_detail"] = f"Sarvam API ({self.model})"
            return local
        except Exception as exc:  # noqa: BLE001
            log.warning("Sarvam analysis unavailable (%s); using fallback", exc)
            local["error"] = str(exc)[:160]
            return local

    async def compose_in_language(
        self, english_text: str, language: str
    ) -> dict[str, Any]:
        """Render an outbound message in the customer's language."""
        if not self.configured or language.startswith("en"):
            return {"text": english_text, "source": "fallback", "translated": False}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/translate",
                    headers=self._headers(),
                    json={
                        "input": english_text,
                        "source_language_code": "en-IN",
                        "target_language_code": language,
                        "mode": "formal",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            return {
                "text": data.get("translated_text") or english_text,
                "source": "sarvam",
                "translated": True,
            }
        except Exception as exc:  # noqa: BLE001
            log.warning("Sarvam compose unavailable (%s); sending English", exc)
            return {
                "text": english_text,
                "source": "fallback",
                "translated": False,
                "error": str(exc)[:160],
            }


def _first_json_object(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from a model response."""
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


sarvam = SarvamAdapter()
