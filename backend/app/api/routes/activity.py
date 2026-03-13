"""
Activity API — event feed + SSE stream.
"""
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser
from app.models import ActivityEvent
from app.services.event_bus import event_bus

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/", response_model=list[ActivityEvent])
def get_activity(
    current_user: CurrentUser,
    limit: int = 50,
) -> Any:
    """Get recent activity events (latest first)."""
    return event_bus.get_recent(limit=limit)


@router.get("/stream")
async def activity_stream(
    current_user: CurrentUser,
) -> StreamingResponse:
    """
    SSE endpoint for real-time activity events.
    Connect with: EventSource('/api/v1/activity/stream')
    """
    return StreamingResponse(
        event_bus.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
