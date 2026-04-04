"""Server-Sent Events (SSE) for Dashboard real-time updates."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter()

# Simple in-memory event bus
_event_queues: list[asyncio.Queue] = []


def broadcast_event(event_type: str, data: dict):
    """Broadcast an event to all connected SSE clients."""
    event = {"type": event_type, "data": data, "timestamp": time.time()}
    for queue in _event_queues:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass  # Drop events for slow consumers


async def _event_generator(queue: asyncio.Queue):
    """Generate SSE stream."""
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'], default=str)}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        if queue in _event_queues:
            _event_queues.remove(queue)


@router.get("/stream")
async def event_stream():
    """SSE endpoint for Dashboard real-time updates.

    Events:
    - task.updated: Task status changed
    - task.created: New task created
    - domain.recalculated: Domain health scores updated
    - report.generated: New report available
    - deploy.verified: Task auto-verified
    - deploy.alert: High-risk task needs attention
    """
    queue = asyncio.Queue(maxsize=100)
    _event_queues.append(queue)

    return StreamingResponse(
        _event_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
