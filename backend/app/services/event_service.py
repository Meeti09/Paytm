"""Mission event recording and the in-process live event bus.

Every meaningful state transition is persisted as a MissionEvent *and* pushed to
subscribers. The Live Mission timeline and the Outcomes screen both read from
these records, so what the UI shows always has a backend record behind it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.models import MissionEvent, utcnow

log = logging.getLogger("pulse.events")

# Canonical event vocabulary (Architecture.md §26).
EVENT_TYPES = {
    "MISSION_CREATED",
    "MISSION_STARTED",
    "LANGUAGE_DETECTED",
    "INTENT_CLASSIFIED",
    "CONTEXT_LOADED",
    "MEMORY_RETRIEVED",
    "CUSTOMER_IDENTIFIED",
    "TRANSACTION_FOUND",
    "MERCHANT_CHECKED",
    "POLICY_RETRIEVED",
    "DECISION_GENERATED",
    "ACTION_PROPOSED",
    "RISK_EVALUATED",
    "APPROVAL_REQUESTED",
    "APPROVAL_GRANTED",
    "APPROVAL_REJECTED",
    "ACTION_EXECUTED",
    "ACTION_VERIFIED",
    "ACTION_FAILED",
    "MESSAGE_SENT",
    "CASE_CREATED",
    "LEAD_DISCOVERED",
    "LEAD_SCORED",
    "LEAD_CONTACTED",
    "LEAD_RESPONDED",
    "LEAD_QUALIFIED",
    "MEETING_BOOKED",
    "MISSION_PAUSED",
    "MISSION_RESUMED",
    "MISSION_COMPLETED",
    "MISSION_FAILED",
    "HUMAN_TAKEOVER",
    "SYSTEM_WARNING",
}


class EventBus:
    """Fan-out of live updates to every connected SSE client.

    `publish` is called both from agent coroutines (on the event loop) and from
    request handlers (on a worker thread), so delivery is always marshalled back
    onto the loop before touching the queues.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, channel: str, data: dict[str, Any]) -> None:
        """Non-blocking broadcast. Safe from a coroutine or a worker thread."""
        message = {"channel": channel, "data": data}
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is not None:
            self._deliver(message)
        elif self._loop is not None:
            self._loop.call_soon_threadsafe(self._deliver, message)
        # No loop bound yet (e.g. during import-time seeding) — nothing is
        # listening, and the event is already persisted, so drop the broadcast.

    def _deliver(self, message: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # A stalled client must never slow the agents down.
                self._subscribers.discard(queue)


bus = EventBus()


def serialize_event(event: MissionEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "mission_id": event.mission_id,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "event_type": event.event_type,
        "actor": event.actor,
        "message": event.message,
        "level": event.level,
        "metadata": event.meta or {},
    }


def record_event(
    session: Session,
    mission_id: str,
    event_type: str,
    message: str,
    *,
    actor: str = "system",
    level: str = "ok",
    meta: dict[str, Any] | None = None,
    publish: bool = True,
) -> MissionEvent:
    """Persist an event and broadcast it to live listeners."""
    if event_type not in EVENT_TYPES:
        log.warning("Unknown event type %s", event_type)

    event = MissionEvent(
        mission_id=mission_id,
        timestamp=utcnow(),
        event_type=event_type,
        actor=actor,
        message=message,
        level=level,
        meta=meta or {},
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    if publish:
        bus.publish("mission_event", serialize_event(event))
    return event


def publish_mission(mission_payload: dict[str, Any]) -> None:
    bus.publish("mission_update", mission_payload)


def publish_approvals_changed() -> None:
    bus.publish("approvals_changed", {})


def publish_outcomes_changed() -> None:
    bus.publish("outcomes_changed", {})
