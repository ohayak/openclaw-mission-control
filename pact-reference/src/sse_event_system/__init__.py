"""SSE Event Bus & File Watching System"""

from .sse_event_system import (
    # Exception classes
    EventBusError,
    WatcherError,
    ParseError,
    SubscriptionError,
    SerializationError,

    # Core functions
    createEventBus,
    emit,
    subscribe,
    unsubscribe,
    destroyEventBus,
    getFileWatcher,
    watch,
    closeFileWatcher,
    handleSSERequest,
    persistEvent,
    getEvents,
    serializeEvent,
    parseEventId,
    createEventPredicate,
    testSSEConnection,
)
