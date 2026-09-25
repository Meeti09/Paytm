"""Paytm Pulse — FastAPI application.

The backend owns mission state, agent orchestration, the policy engine,
persistence and the execution hand-off. The frontend never decides whether an
action is safe.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents import orchestrator
from app.api import approvals, demo, missions, outcomes, paytm, stream
from app.config import integration_status, settings
from app.db import SessionLocal, engine, init_db
from app.demo.seed import ensure_seeded
from app.policy.risk import current_policy
from app.services.event_service import bus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pulse")


@asynccontextmanager
async def lifespan(_: FastAPI):
    loop = asyncio.get_running_loop()
    orchestrator.bind_loop(loop)
    bus.bind_loop(loop)

    if engine.url.get_backend_name() == "sqlite":
        # WAL keeps the agent tasks and the API from blocking each other.
        with engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            conn.exec_driver_sql("PRAGMA busy_timeout=5000")

    init_db()
    session = SessionLocal()
    try:
        if ensure_seeded(session):
            log.info("Seeded the demo dataset")
    finally:
        session.close()

    for name, state in integration_status().items():
        log.info("integration %-7s %-10s %s", name, state["mode"], state["detail"])
    log.info(
        "autonomy policy: approval required above ₹%s (demo policy)",
        settings.refund_approval_threshold,
    )

    yield

    orchestrator.cancel_all()


app = FastAPI(
    title="Paytm Pulse API",
    description=(
        "AI workforce for Paytm — Resolve and Grow. Prototype with a simulated "
        "Paytm integration boundary; all records are fictional demo data."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(missions.router)
app.include_router(approvals.router)
app.include_router(outcomes.router)
app.include_router(demo.router)
app.include_router(stream.router)
app.include_router(paytm.router)


@app.get("/api/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "demo_mode": settings.demo_mode,
        "integrations": integration_status(),
        "policy": current_policy(),
        "disclosure": (
            "Simulated Paytm integration boundary. No production Paytm access."
        ),
    }
