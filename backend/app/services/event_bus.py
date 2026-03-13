"""
In-memory pub/sub event bus for SSE events.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from app.models import ActivityEvent


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []
        self._recent_events: list[ActivityEvent] = []
        self._max_recent = 200

    def publish(self, event: ActivityEvent) -> None:
        """Publish an event to all subscribers."""
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_recent:
            self._recent_events = self._recent_events[-self._max_recent:]

        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def get_recent(self, limit: int = 50) -> list[ActivityEvent]:
        return list(reversed(self._recent_events[-limit:]))

    async def subscribe(self) -> AsyncIterator[str]:
        """Async generator that yields SSE-formatted strings."""
        q: asyncio.Queue[ActivityEvent] = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    data = json.dumps(event.model_dump())
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        finally:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def emit_activity(
        self,
        event_type: str,
        message: str,
        agent_id: str | None = None,
        project_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        event = ActivityEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            agent_id=agent_id,
            project_id=project_id,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_metadata=metadata,
        )
        self.publish(event)


# Global singleton
event_bus = EventBus()
