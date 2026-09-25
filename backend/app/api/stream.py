"""Server-Sent Events stream.

One stream carries every live update: mission events, mission state changes and
approval/outcome invalidations. The UI renders only what arrives here, so a tick
on screen always corresponds to a record in the database.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.event_service import bus

log = logging.getLogger("pulse.stream")

router = APIRouter(prefix="/api", tags=["stream"])

HEARTBEAT_SECONDS = 15


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    queue = bus.subscribe()

    async def generator():
        try:
            yield _sse("connected", {"ok": True})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_SECONDS
                    )
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield _sse(message["channel"], message["data"])
        except asyncio.CancelledError:  # client went away
            raise
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
