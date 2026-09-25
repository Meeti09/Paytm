"""Agent orchestration.

Missions run as asyncio tasks inside the API process. An agent that reaches an
approval boundary *ends its task* rather than parking on a lock — when a human
decides, a fresh continuation task picks the mission back up. That keeps the
approval boundary a real stop, not a blocked thread.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.agents.base import MissionAborted
from app.agents.grow import GrowAgent
from app.agents.resolve import ResolveAgent
from app.db import SessionLocal
from app.models.models import Mission, utcnow
from app.services.event_service import (
    publish_mission,
    publish_outcomes_changed,
    record_event,
)
from app.services.mission_service import serialize_mission, update_mission

log = logging.getLogger("pulse.orchestrator")

_tasks: dict[str, asyncio.Task] = {}
_loop: asyncio.AbstractEventLoop | None = None

AGENTS = {"resolve": ResolveAgent, "grow": GrowAgent}


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Remember the application event loop.

    Request handlers are sync functions executed on a worker thread, so they
    cannot create tasks directly — work is scheduled back onto this loop.
    """
    global _loop
    _loop = loop


def build_agent(agent: str, mission_id: str):
    cls = AGENTS.get(agent)
    if cls is None:
        raise ValueError(f"Unknown agent '{agent}'")
    return cls(mission_id)


def is_running(mission_id: str) -> bool:
    task = _tasks.get(mission_id)
    return bool(task and not task.done())


async def _execute(mission_id: str, method: str, *args: Any) -> None:
    session = SessionLocal()
    try:
        mission = session.get(Mission, mission_id)
        if mission is None:
            return
        agent = build_agent(mission.agent, mission_id)
        await getattr(agent, method)(session, *args)
    except asyncio.CancelledError:
        log.info("Mission %s cancelled", mission_id)
        raise
    except MissionAborted as exc:
        log.info("Mission %s stopped: %s", mission_id, exc)
    except Exception as exc:  # noqa: BLE001 - surface, never swallow
        log.exception("Mission %s crashed", mission_id)
        _mark_failed(mission_id, str(exc)[:300])
    finally:
        session.close()
        if _tasks.get(mission_id) is asyncio.current_task():
            _tasks.pop(mission_id, None)


def _mark_failed(mission_id: str, reason: str) -> None:
    session = SessionLocal()
    try:
        mission = session.get(Mission, mission_id)
        if mission is None or mission.status in ("completed", "failed"):
            return
        record_event(
            session,
            mission_id,
            "MISSION_FAILED",
            f"Mission failed: {reason}",
            actor=mission.agent,
            level="error",
        )
        update_mission(
            session,
            mission,
            status="failed",
            result="failed",
            result_label=reason[:160],
            error=reason,
            progress=100,
            completed_at=utcnow(),
        )
    except Exception:  # noqa: BLE001
        log.exception("Could not mark mission %s failed", mission_id)
    finally:
        session.close()


def _spawn(mission_id: str, method: str, *args: Any) -> None:
    def create() -> None:
        existing = _tasks.get(mission_id)
        if existing and not existing.done():
            log.warning("Mission %s already has a running task", mission_id)
            return
        _tasks[mission_id] = asyncio.create_task(_execute(mission_id, method, *args))

    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is not None:
        create()
    elif _loop is not None:
        _loop.call_soon_threadsafe(create)
    else:
        raise RuntimeError("Agent orchestrator has no event loop bound")


def start_mission(mission_id: str) -> None:
    _spawn(mission_id, "run")


def resume_after_approval(mission_id: str, approval_id: str, reviewer: str) -> None:
    _spawn(mission_id, "_continue_approved", approval_id, reviewer)


def resume_after_rejection(mission_id: str, approval_id: str, reviewer: str) -> None:
    _spawn(mission_id, "_continue_rejected", approval_id, reviewer)


def submit_reply(mission_id: str, lead_id: str, text: str) -> None:
    _spawn(mission_id, "handle_reply", lead_id, text)


def stop_mission(mission_id: str) -> None:
    task = _tasks.pop(mission_id, None)
    if not task or task.done():
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        if _loop is not None:
            _loop.call_soon_threadsafe(task.cancel)
        return
    task.cancel()


def cancel_all() -> None:
    for mission_id in list(_tasks):
        stop_mission(mission_id)


def retry_mission(mission_id: str) -> None:
    _spawn(mission_id, "retry")


def takeover(mission_id: str, operator: str) -> None:
    """A human takes ownership: stop the agent and record the hand-off."""
    stop_mission(mission_id)
    session = SessionLocal()
    try:
        mission = session.get(Mission, mission_id)
        if mission is None:
            return
        record_event(
            session,
            mission_id,
            "HUMAN_TAKEOVER",
            f"{operator} took over the mission",
            actor="human",
            level="warn",
        )
        update_mission(
            session,
            mission,
            status="human_takeover",
            stage="HUMAN_TAKEOVER",
            progress=100,
            human_involved=True,
            result="handled_by_human",
            result_label=f"Taken over by {operator}",
            completed_at=utcnow(),
        )
        publish_mission(serialize_mission(session, mission))
        publish_outcomes_changed()
    finally:
        session.close()


def pause(mission_id: str) -> None:
    stop_mission(mission_id)
    session = SessionLocal()
    try:
        mission = session.get(Mission, mission_id)
        if mission is None or mission.status in ("completed", "failed", "human_takeover"):
            return
        record_event(
            session,
            mission_id,
            "MISSION_PAUSED",
            "Mission paused by operator",
            actor="human",
            level="warn",
        )
        update_mission(session, mission, status="paused")
    finally:
        session.close()
