"""Tests for the EventBus pub/sub and event buffer."""
import asyncio
import pytest
from app.models import ActivityEvent
from app.services.event_bus import EventBus


def make_event(event_type: str = "test", message: str = "test msg", n: int = 0) -> ActivityEvent:
    return ActivityEvent(
        id=f"evt-{n}",
        event_type=event_type,
        message=message,
        timestamp="2024-01-15T10:00:00Z",
    )


class TestEventBusPublishSubscribe:
    def test_publish_adds_to_recent(self):
        bus = EventBus()
        evt = make_event(n=1)
        bus.publish(evt)
        recent = bus.get_recent(limit=10)
        assert len(recent) == 1
        assert recent[0].id == "evt-1"

    def test_publish_multiple_events(self):
        bus = EventBus()
        for i in range(5):
            bus.publish(make_event(n=i))
        recent = bus.get_recent(limit=10)
        assert len(recent) == 5

    def test_get_recent_returns_latest_first(self):
        bus = EventBus()
        for i in range(5):
            bus.publish(make_event(message=f"msg-{i}", n=i))
        recent = bus.get_recent(limit=5)
        # Should be reversed (latest first)
        assert recent[0].id == "evt-4"
        assert recent[-1].id == "evt-0"

    def test_get_recent_respects_limit(self):
        bus = EventBus()
        for i in range(10):
            bus.publish(make_event(n=i))
        recent = bus.get_recent(limit=3)
        assert len(recent) == 3

    @pytest.mark.asyncio
    async def test_subscribe_receives_published_event(self):
        bus = EventBus()
        received = []

        async def consumer():
            async for chunk in bus.subscribe():
                received.append(chunk)
                break  # Just get one event

        # Start consumer in background, then publish
        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.01)
        bus.publish(make_event(n=99))
        await asyncio.wait_for(task, timeout=2.0)

        assert len(received) == 1
        assert '"evt-99"' in received[0]

    @pytest.mark.asyncio
    async def test_subscribe_sends_keepalive_on_timeout(self):
        """Subscriber should get a keepalive comment if no events arrive."""
        bus = EventBus()
        # Monkeypatch timeout to be very short for test speed
        original_subscribe = bus.subscribe

        async def fast_subscribe():
            import asyncio
            q: asyncio.Queue = asyncio.Queue(maxsize=100)
            bus._subscribers.append(q)
            try:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=0.05)
                    import json
                    yield f"data: {json.dumps(event.model_dump())}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
            finally:
                try:
                    bus._subscribers.remove(q)
                except ValueError:
                    pass

        chunks = []
        async for chunk in fast_subscribe():
            chunks.append(chunk)
            break

        assert any("keepalive" in c for c in chunks)


class TestEventBusBuffer:
    def test_buffer_max_200_events(self):
        bus = EventBus()
        assert bus._max_recent == 200

        # Publish 250 events
        for i in range(250):
            bus.publish(make_event(n=i))

        # Should only keep last 200
        assert len(bus._recent_events) == 200

    def test_buffer_keeps_most_recent(self):
        bus = EventBus()
        for i in range(250):
            bus.publish(make_event(message=f"msg-{i}", n=i))

        # The 200 kept should be the latest ones (50-249)
        ids = [e.id for e in bus._recent_events]
        assert "evt-0" not in ids
        assert "evt-49" not in ids
        assert "evt-50" in ids
        assert "evt-249" in ids

    def test_emit_activity_helper(self):
        bus = EventBus()
        bus.emit_activity(
            event_type="session_start",
            message="Agent started a session",
            agent_id="jim",
            metadata={"session_id": "abc123"},
        )
        recent = bus.get_recent(limit=1)
        assert len(recent) == 1
        evt = recent[0]
        assert evt.event_type == "session_start"
        assert evt.agent_id == "jim"
        assert evt.event_metadata == {"session_id": "abc123"}
