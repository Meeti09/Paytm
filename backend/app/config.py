"""Application configuration.

All secrets come from the environment. Nothing here contains a real credential,
and no secret is ever returned to the browser — see `integration_status()` for
the only integration information the frontend is allowed to see.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Application -------------------------------------------------
    node_env: str = "development"
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Optional regex for hosted frontends whose origin varies — e.g. Vercel
    # preview deployments: https://paytm-pulse-.*\.vercel\.app
    cors_origin_regex: str = ""

    # ---- Database ----------------------------------------------------
    # Empty -> local SQLite file. A PostgreSQL URL works unchanged.
    database_url: str = ""

    # ---- LLM ---------------------------------------------------------
    # provider: anthropic | openai | openai_compatible | sarvam | "" (offline)
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""

    # ---- Sarvam (India-native language layer) ------------------------
    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_model: str = "sarvam-m"

    # ---- Cognee (contextual memory) ----------------------------------
    cognee_api_url: str = ""
    cognee_api_key: str = ""

    # ---- n8n (execution layer) ---------------------------------------
    n8n_base_url: str = ""
    n8n_api_key: str = ""
    n8n_webhook_prefix: str = "/webhook/paytm-pulse"

    # ---- Demo policy (hackathon policy, not Paytm production policy) --
    refund_approval_threshold: int = 1000
    account_actions_require_approval: bool = True
    negative_sentiment_requires_review: bool = True
    irreversible_actions_require_approval: bool = True
    unknown_permissions_require_approval: bool = True

    # ---- Grow tuning --------------------------------------------------
    # A lead is qualified at/above this score...
    lead_qualification_threshold: int = 75
    # ...and only qualified leads at/above this score get outreach first.
    lead_outreach_threshold: int = 80

    # ---- Internal service auth ----------------------------------------
    # Guards the mutating /paytm/* boundary endpoints so only the execution
    # layer (n8n) can call them — never a browser. Generated at boot if unset.
    internal_api_key: str = ""

    # ---- Demo ---------------------------------------------------------
    demo_mode: bool = True
    # Pacing between agent steps so the live timeline is legible on stage.
    agent_step_delay_ms: int = 550

    # ---- Derived -------------------------------------------------------
    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            url = self.database_url
            # Managed Postgres providers hand out `postgres://`, which
            # SQLAlchemy does not accept. Normalise to the psycopg 3 dialect —
            # the driver shipped in requirements.txt.
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            return url
        return f"sqlite:///{(BACKEND_DIR / 'pulse.db').as_posix()}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def step_delay(self) -> float:
        return max(self.agent_step_delay_ms, 0) / 1000.0


@lru_cache
def get_settings() -> Settings:
    resolved = Settings()
    if not resolved.internal_api_key:
        # Ephemeral per-process secret. Never sent to the frontend.
        resolved.internal_api_key = secrets.token_urlsafe(24)
    return resolved


settings = get_settings()


def integration_status() -> dict[str, dict[str, str]]:
    """Safe, secret-free description of how each integration is wired.

    The UI renders this so a judge can see exactly which parts are live and
    which are running on the local deterministic fallback. It never leaks keys.
    """

    def state(configured: bool, live_label: str, fallback_label: str) -> dict[str, str]:
        return {
            "mode": "live" if configured else "fallback",
            "detail": live_label if configured else fallback_label,
        }

    return {
        "llm": state(
            bool(settings.llm_api_key and settings.llm_provider),
            f"{settings.llm_provider}:{settings.llm_model or 'default'}",
            "Deterministic policy reasoner",
        ),
        "sarvam": state(
            bool(settings.sarvam_api_key),
            f"Sarvam API ({settings.sarvam_model})",
            "Local language + intent classifier",
        ),
        "cognee": state(
            bool(settings.cognee_api_url),
            "Cognee service",
            "Local context store",
        ),
        "n8n": state(
            bool(settings.n8n_base_url),
            "n8n webhooks",
            "Local workflow runner",
        ),
        "paytm": {
            "mode": "simulated",
            "detail": "Simulated Paytm integration boundary",
        },
    }
