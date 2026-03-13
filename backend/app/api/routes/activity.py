"""
Activity API — event feed + SSE stream.
"""
from typing import Any, Optional

import jwt
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.api.deps import CurrentUser, get_db
from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import ActivityEvent, TokenPayload, User
from app.services.event_bus import event_bus

router = APIRouter(prefix="/activity", tags=["activity"])


def _get_user_from_token(token: str) -> User:
    """Validate a JWT token string and return the corresponding user."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    with Session(engine) as session:
        user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


@router.get("/", response_model=list[ActivityEvent])
def get_activity(
    current_user: CurrentUser,
    limit: int = 50,
) -> Any:
    """Get recent activity events (latest first)."""
    return event_bus.get_recent(limit=limit)


@router.get("/stream")
async def activity_stream(
    token: Optional[str] = Query(default=None),
    current_user: Optional[CurrentUser] = None,
) -> StreamingResponse:
    """
    SSE endpoint for real-time activity events.

    Supports two auth methods:
    - Standard Bearer token via Authorization header (current_user dependency)
    - Query param token for EventSource: GET /api/v1/activity/stream?token=<jwt>

    Connect with:
      const es = new EventSource(`/api/v1/activity/stream?token=${jwt}`);
    """
    # EventSource cannot send custom headers, so accept token via query param
    if current_user is None and token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Pass token query param for SSE.",
        )

    if current_user is None and token is not None:
        # Validate the query param JWT
        _get_user_from_token(token)

    return StreamingResponse(
        event_bus.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
