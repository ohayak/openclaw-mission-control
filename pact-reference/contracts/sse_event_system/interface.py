# === SSE Event Bus & File Watching (sse_event_system) v1 ===
# Real-time event infrastructure providing in-process pub/sub event bus, filesystem watching with diff synthesis, SSE streaming endpoint, and event persistence. Watches OpenClaw and PACT directories, multiplexes typed events (agent actions, PACT transitions, task changes, errors), and streams to clients with filtering support. HMR-safe singleton pattern with graceful shutdown.

# Module invariants:
#   - Event IDs are unique within the system (enforced by nanoid/uuid)
#   - All events have version='v1' (schema versioning for future evolution)
#   - Event bus state transitions: active -> destroying -> destroyed (one-way)
#   - FileWatcher state transitions: initializing -> ready|error, any -> closed
#   - Only one FileWatcher instance exists per process (singleton via globalThis)
#   - Event timestamps are strictly increasing within a single emit sequence
#   - Subscription handlers never block emit() (async handlers run in background)
#   - SSE connections emit exactly one connection_opened event per lifecycle
#   - Persisted events older than EVENT_RETENTION_DAYS are automatically pruned
#   - Event bus emit() never throws (errors logged, persistence non-blocking)
#   - File watcher errors emit system.watcher_error events (never crash process)
#   - Parse errors emit system.parse_error events with file path context
#   - SSE heartbeat ensures connection liveness within 2*HEARTBEAT_INTERVAL_MS
#   - All Event payloads are JSON-serializable (no circular refs, Functions, Symbols)
#   - EventPredicate filters are pure functions (no side effects, deterministic)

EventId = primitive  # Branded string identifier for events (nanoid or UUID)

ConnectionId = primitive  # Branded string identifier for SSE connections

Timestamp = primitive  # ISO 8601 timestamp string

EventVersion = primitive  # String literal 'v1' for event schema version

class EventType(Enum):
    """Namespaced event type discriminator"""
    agent.started = "agent.started"
    agent.stopped = "agent.stopped"
    agent.error = "agent.error"
    agent.action_completed = "agent.action_completed"
    pact.transition = "pact.transition"
    pact.component_completed = "pact.component_completed"
    pact.contract_validated = "pact.contract_validated"
    pact.error = "pact.error"
    task.created = "task.created"
    task.updated = "task.updated"
    task.completed = "task.completed"
    task.deleted = "task.deleted"
    system.watcher_ready = "system.watcher_ready"
    system.watcher_error = "system.watcher_error"
    system.parse_error = "system.parse_error"
    system.connection_opened = "system.connection_opened"
    system.shutdown = "system.shutdown"
    system.heartbeat = "system.heartbeat"

class BaseEvent:
    """Common fields for all events"""
    id: EventId                              # required, Unique event identifier
    timestamp: Timestamp                     # required, ISO 8601 timestamp when event occurred
    type: EventType                          # required, Event type discriminator
    version: EventVersion                    # required, Event schema version, always 'v1'

class AgentEventPayload:
    """Payload for agent.* events"""
    agent_id: str                            # required, Agent identifier
    action: str = None                       # optional, Action name for action_completed events
    error_message: str = None                # optional, Error message for error events
    metadata: dict = None                    # optional, Additional context data

class AgentEvent:
    """Agent lifecycle and action events"""
    id: EventId                              # required
    timestamp: Timestamp                     # required
    type: EventType                          # required, regex(^agent\.)
    version: EventVersion                    # required
    payload: AgentEventPayload               # required

class PactEventPayload:
    """Payload for pact.* events"""
    project_id: str                          # required, PACT project identifier
    component_id: str = None                 # optional, Component identifier for component-level events
    from_state: str = None                   # optional, Previous state for transition events
    to_state: str = None                     # optional, New state for transition events
    error_message: str = None                # optional, Error message for error events
    metadata: dict = None                    # optional, Additional context data

class PactEvent:
    """PACT state transition and validation events"""
    id: EventId                              # required
    timestamp: Timestamp                     # required
    type: EventType                          # required, regex(^pact\.)
    version: EventVersion                    # required
    payload: PactEventPayload                # required

class TaskEventPayload:
    """Payload for task.* events"""
    task_id: str                             # required, Task identifier
    title: str = None                        # optional, Task title
    status: str = None                       # optional, Task status (pending/in_progress/completed/cancelled)
    assigned_agent: str = None               # optional, Assigned agent identifier
    metadata: dict = None                    # optional, Additional context data

class TaskEvent:
    """Task lifecycle events"""
    id: EventId                              # required
    timestamp: Timestamp                     # required
    type: EventType                          # required, regex(^task\.)
    version: EventVersion                    # required
    payload: TaskEventPayload                # required

class SystemEventPayload:
    """Payload for system.* events"""
    connection_id: ConnectionId = None       # optional, Connection identifier for connection events
    file_path: str = None                    # optional, File path for watcher/parse events
    error_message: str = None                # optional, Error message for error events
    line: int = None                         # optional, Line number for parse errors
    column: int = None                       # optional, Column number for parse errors
    watched_paths: list = None               # optional, List of watched paths for watcher_ready events
    metadata: dict = None                    # optional, Additional context data

class SystemEvent:
    """System lifecycle and infrastructure events"""
    id: EventId                              # required
    timestamp: Timestamp                     # required
    type: EventType                          # required, regex(^system\.)
    version: EventVersion                    # required
    payload: SystemEventPayload              # required

Event = AgentEvent | PactEvent | TaskEvent | SystemEvent

EventPredicate = primitive  # Function type (event: Event) => boolean for filtering

EventHandler = primitive  # Function type (event: Event) => void | Promise<void>

UnsubscribeFn = primitive  # Function type () => void to unsubscribe from event bus

SubscriptionId = primitive  # Branded string identifier for subscriptions

class EventBusState(Enum):
    """Event bus lifecycle state"""
    active = "active"
    destroying = "destroying"
    destroyed = "destroyed"

class FileWatcherState(Enum):
    """File watcher lifecycle state"""
    initializing = "initializing"
    ready = "ready"
    error = "error"
    closed = "closed"

class WatchOptions:
    """Options for filesystem watching"""
    ignored: list = None                     # optional, Glob patterns to ignore (e.g., node_modules, .git)
    persistent: bool = true                  # optional, Keep process running while watching
    ignoreInitial: bool = true               # optional, Ignore initial add events
    awaitWriteFinish: dict = None            # optional, Options for debouncing writes {stabilityThreshold: number, pollInterval: number}

class SSEFilterParams:
    """Query parameters for SSE endpoint filtering"""
    type: str = None                         # optional, regex(^[a-z]+([.][a-z_]+)?$), Filter by event type prefix (e.g., 'agent', 'pact.transition')
    project: str = None                      # optional, Filter by project_id in payload
    agent: str = None                        # optional, Filter by agent_id in payload
    lastEventId: str = None                  # optional, Resume from last received event ID

class PaginationParams:
    """Pagination parameters for event history queries"""
    limit: int = 100                         # optional, range(1..1000)
    offset: int = 0                          # optional, range(0..)
    order: str = desc                        # optional, regex(^(asc|desc)$)

class EventFilters:
    """Filter criteria for event history queries"""
    type: str = None                         # optional, Filter by event type prefix
    project_id: str = None                   # optional, Filter by project_id in payload
    agent_id: str = None                     # optional, Filter by agent_id in payload
    since: Timestamp = None                  # optional, Filter events after this timestamp
    until: Timestamp = None                  # optional, Filter events before this timestamp

class EventBusConfig:
    """Configuration constants for event bus"""
    HEARTBEAT_INTERVAL_MS: int               # required, SSE heartbeat interval (15000-30000ms)
    DEBOUNCE_MS: int                         # required, File watcher debounce delay (100-300ms)
    EVENT_RETENTION_DAYS: int                # required, Days to retain events in database
    WATCHED_FILES: list                      # required, Glob patterns for watched files
    IGNORED_PATTERNS: list                   # required, Glob patterns to ignore when watching

class EventBusError:
    """Base error for event bus operations"""
    message: str                             # required
    cause: any = None                        # optional, Underlying error cause

class WatcherError:
    """File watcher error with file context"""
    message: str                             # required
    filePath: str                            # required, Path to file that caused error
    cause: any = None                        # optional

class ParseError:
    """File parsing error with location context"""
    message: str                             # required
    filePath: str                            # required, Path to file that failed to parse
    line: int = None                         # optional, Line number of parse error
    column: int = None                       # optional, Column number of parse error
    cause: any = None                        # optional

class SubscriptionError:
    """Subscription management error"""
    message: str                             # required
    subscriptionId: SubscriptionId = None    # optional
    cause: any = None                        # optional

class SerializationError:
    """Event serialization error with path to problematic field"""
    message: str                             # required
    path: str = None                         # optional, JSON path to field that failed serialization
    cause: any = None                        # optional

class MockEventBus:
    """Mock event bus interface for testing"""
    emit: any                                # required, Spy/stub for emit function
    subscribe: any                           # required, Spy/stub for subscribe function
    unsubscribe: any                         # required, Spy/stub for unsubscribe function
    destroy: any                             # required, Spy/stub for destroy function
    state: EventBusState                     # required

class MockFileWatcher:
    """Mock file watcher interface for testing"""
    watch: any                               # required, Spy/stub for watch function
    close: any                               # required, Spy/stub for close function
    state: FileWatcherState                  # required
    triggerChange: any = None                # optional, Test helper to simulate file changes

def createEventBus(
    config: EventBusConfig = None,
) -> any:
    """
    Factory function to create a new EventBus instance. Returns an event bus with active state, empty subscription registry, and ready for emit/subscribe operations.

    Postconditions:
      - Returned bus has state='active'
      - Subscription registry is empty
      - Bus is ready to accept emit/subscribe calls

    Side effects: none
    Idempotent: no
    """
    ...

def emit(
    event: Event,
) -> None:
    """
    Publish an event to the event bus. Synchronously notifies all matching subscribers based on their predicate filters. Does not throw on handler errors (logs instead). Non-blocking for persistence (fire-and-forget).

    Preconditions:
      - Event bus state must be 'active'
      - Event must pass Zod schema validation
      - Event.id must be unique (generated via nanoid/uuid)
      - Event.timestamp must be valid ISO 8601
      - Event.version must equal 'v1'

    Postconditions:
      - All matching subscribers have been invoked
      - Event persistence attempted (async, non-blocking)
      - Handler errors logged but do not propagate

    Errors:
      - BusDestroyed (EventBusError): Event bus state is 'destroyed' or 'destroying'
          message: Cannot emit event: bus is destroyed
      - InvalidEvent (EventBusError): Event fails Zod schema validation
          message: Event failed validation
          cause: Zod validation error

    Side effects: none
    Idempotent: no
    """
    ...

def subscribe(
    predicate: EventPredicate = None,
    handler: EventHandler,
) -> UnsubscribeFn:
    """
    Register an event handler with optional predicate filter. Returns unsubscribe function. Handler is invoked synchronously when matching events are emitted. Predicate defaults to (event) => true (match all).

    Preconditions:
      - Event bus state must be 'active'
      - Handler must be a function

    Postconditions:
      - Subscription registered with unique SubscriptionId
      - Handler will be invoked for future matching events
      - Returned unsubscribe function removes this subscription when called

    Errors:
      - BusDestroyed (SubscriptionError): Event bus state is 'destroyed'
          message: Cannot subscribe: bus is destroyed
      - InvalidHandler (SubscriptionError): Handler is not a function
          message: Handler must be a function

    Side effects: none
    Idempotent: no
    """
    ...

def unsubscribe(
    subscriptionId: SubscriptionId,
) -> None:
    """
    Remove a subscription by ID. Idempotent (safe to call multiple times). No-op if subscription ID not found.

    Postconditions:
      - Subscription removed from registry (if existed)
      - Handler will no longer be invoked for future events

    Side effects: none
    Idempotent: yes
    """
    ...

def destroyEventBus(
    signal: any = None,
) -> None:
    """
    Gracefully shutdown event bus. Unsubscribes all handlers, waits for in-flight handler executions (respecting AbortSignal), emits system.shutdown event, sets state to 'destroyed'. Idempotent.

    Postconditions:
      - State set to 'destroyed'
      - All subscriptions cleared
      - system.shutdown event emitted before clearing subscriptions
      - No future emit/subscribe operations allowed

    Errors:
      - DestroyAborted (EventBusError): AbortSignal is triggered during shutdown
          message: Event bus destruction aborted

    Side effects: none
    Idempotent: yes
    """
    ...

def getFileWatcher() -> any:
    """
    Singleton factory for FileWatcher. First call creates watcher with chokidar, subsequent calls return existing instance. Uses globalThis pattern for HMR safety in dev mode. Returns watcher in 'initializing' or 'ready' state.

    Postconditions:
      - If first call: new FileWatcher created and stored in globalThis
      - If subsequent call: existing FileWatcher returned
      - Returned watcher state is 'initializing', 'ready', or 'error'
      - Only one watcher instance exists per process

    Side effects: none
    Idempotent: no
    """
    ...

def watch(
    paths: list,
    options: WatchOptions = None,
) -> None:
    """
    Start watching filesystem paths with chokidar. Synthesizes events from file changes (add/change/unlink), emits parse_error on malformed files, watcher_ready when initialization completes. Debounces file changes per DEBOUNCE_MS config. Idempotent (calling multiple times with same paths is safe).

    Preconditions:
      - FileWatcher state must not be 'closed'
      - Paths must be valid file system paths or globs

    Postconditions:
      - Watcher state transitions to 'ready' on successful initialization
      - system.watcher_ready event emitted with watched_paths in payload
      - File change events debounced per DEBOUNCE_MS
      - Parse errors result in system.parse_error events (non-fatal)

    Errors:
      - WatcherClosed (WatcherError): FileWatcher state is 'closed'
          message: Cannot watch: watcher is closed
          filePath: <none>
      - InvalidPath (WatcherError): Paths list is empty or contains invalid paths
          message: Invalid watch paths
          filePath: <invalid_path>
      - ChokidarInitFailed (WatcherError): Chokidar fails to initialize (permissions, missing dirs)
          message: Chokidar initialization failed
          filePath: <path>
          cause: chokidar error

    Side effects: none
    Idempotent: yes
    """
    ...

def closeFileWatcher() -> None:
    """
    Shutdown file watcher and release chokidar resources. Stops all filesystem watching, emits no further events, sets state to 'closed'. Idempotent (safe to call multiple times).

    Postconditions:
      - Watcher state set to 'closed'
      - Chokidar instance closed and resources released
      - No further file change events emitted
      - Singleton can be re-initialized via getFileWatcher() after close

    Side effects: none
    Idempotent: yes
    """
    ...

def handleSSERequest(
    request: any,
) -> any:
    """
    Next.js Route Handler for GET /api/events. Validates query params with Zod, creates SSE stream (text/event-stream), subscribes to event bus with filters, sends events in SSE format (id:/event:/data:/retry:), emits heartbeat per HEARTBEAT_INTERVAL_MS, handles client disconnect cleanup, supports Last-Event-ID header for reconnection.

    Preconditions:
      - Request method is GET
      - Event bus is active and ready
      - Query params validate against SSEFilterParams schema

    Postconditions:
      - Returns Response with headers: Content-Type: text/event-stream, Cache-Control: no-cache, Connection: keep-alive
      - system.connection_opened event emitted with new ConnectionId
      - Client receives filtered events in SSE format
      - Heartbeat events sent every HEARTBEAT_INTERVAL_MS
      - Subscription cleaned up on client disconnect
      - If lastEventId provided: resume from that event (fetch from persistence layer)

    Errors:
      - InvalidQueryParams (EventBusError): Query params fail Zod SSEFilterParams validation
          status: 400
          message: Invalid filter parameters
      - MethodNotAllowed (EventBusError): Request method is not GET
          status: 405
          message: Method not allowed
      - EventBusUnavailable (EventBusError): Event bus is not active or destroyed
          status: 503
          message: Event bus unavailable

    Side effects: none
    Idempotent: no
    """
    ...

def persistEvent(
    event: Event,
) -> None:
    """
    Asynchronously persist event to SQLite activity_events table. Called non-blocking from emit(). Uses Promise.allSettled pattern to avoid blocking event propagation. Logs errors but does not throw.

    Preconditions:
      - Event must be valid (already validated in emit)
      - SQLite database connection available

    Postconditions:
      - Event inserted into activity_events table (id, timestamp, type, payload JSON)
      - Old events beyond EVENT_RETENTION_DAYS pruned (async cleanup)
      - Errors logged but do not propagate to caller

    Errors:
      - SerializationFailed (SerializationError): Event payload cannot be serialized to JSON (circular refs, BigInt without toJSON)
          message: Failed to serialize event
          path: payload.someField
      - DatabaseWriteFailed (EventBusError): SQLite insert fails (disk full, constraint violation)
          message: Database write failed
          cause: sqlite error

    Side effects: none
    Idempotent: no
    """
    ...

def getEvents(
    filters: EventFilters = None,
    pagination: PaginationParams = None,
) -> list:
    """
    Query event history from SQLite activity_events table with filters and pagination. Returns events matching type/project/agent/time filters, ordered by timestamp, limited per pagination params. Used for /api/events/history and SSE reconnection (lastEventId).

    Preconditions:
      - Filters validated against EventFilters schema
      - Pagination validated against PaginationParams schema
      - SQLite database connection available

    Postconditions:
      - Returns list of Event objects matching filters
      - Events ordered by timestamp per pagination.order
      - Result limited per pagination.limit
      - Empty list if no matches

    Errors:
      - InvalidFilters (EventBusError): Filters fail EventFilters schema validation
          message: Invalid event filters
      - DatabaseReadFailed (EventBusError): SQLite query fails (corrupted db, permissions)
          message: Database read failed
          cause: sqlite error
      - DeserializationFailed (SerializationError): Stored JSON payload cannot be parsed back to Event
          message: Failed to deserialize event from database

    Side effects: none
    Idempotent: no
    """
    ...

def serializeEvent(
    event: Event,
) -> str:
    """
    Convert Event object to SSE-compatible JSON string. Handles special types: BigInt (via toJSON or string conversion), Date (ISO 8601), Error (message + stack). Detects circular references and throws SerializationError with path to problematic field.

    Preconditions:
      - Event is a valid Event object (validated by Zod)

    Postconditions:
      - Returns valid JSON string
      - BigInt fields converted to string or toJSON result
      - Date fields converted to ISO 8601 strings
      - Error fields converted to {message, stack} objects

    Errors:
      - CircularReference (SerializationError): Event payload contains circular references
          message: Circular reference detected
          path: payload.metadata.circularField
      - UnsupportedType (SerializationError): Event payload contains non-serializable type (Symbol, Function)
          message: Unsupported type in event payload
          path: payload.someField

    Side effects: none
    Idempotent: no
    """
    ...

def parseEventId(
    lastEventId: str,
) -> EventId:
    """
    Parse Last-Event-ID header value into EventId. Validates format (nanoid or UUID), returns null if invalid. Used for SSE reconnection to resume from last received event.

    Postconditions:
      - Returns EventId if valid format
      - Returns null if invalid or empty string

    Side effects: none
    Idempotent: no
    """
    ...

def createEventPredicate(
    filterParams: SSEFilterParams,
) -> EventPredicate:
    """
    Factory to create EventPredicate filter functions from SSEFilterParams. Builds predicate that checks event.type prefix, payload.project_id, payload.agent_id. Used by SSE endpoint to convert query params to subscription filter.

    Preconditions:
      - filterParams validated against SSEFilterParams schema

    Postconditions:
      - Returns function (event: Event) => boolean
      - Returned predicate checks event.type starts with filterParams.type (if provided)
      - Returned predicate checks payload.project_id === filterParams.project (if provided)
      - Returned predicate checks payload.agent_id === filterParams.agent (if provided)
      - All filters are AND-combined

    Side effects: none
    Idempotent: no
    """
    ...

def testSSEConnection(
    baseUrl: str,
    timeoutMs: int = 5000,
) -> bool:
    """
    Integration test helper that verifies SSE endpoint connectivity. Creates EventSource client, subscribes to /api/events, waits for system.connection_opened event, then disconnects. Returns true if connection successful, false otherwise. Used for health checks (AC6).

    Preconditions:
      - Next.js app is running and serving /api/events
      - Event bus is active

    Postconditions:
      - Returns true if connection_opened event received within timeout
      - Returns false if timeout or connection error
      - EventSource connection closed after test

    Errors:
      - ConnectionTimeout (EventBusError): No connection_opened event received within timeoutMs
          message: SSE connection test timed out
      - ConnectionFailed (EventBusError): EventSource reports error event
          message: SSE connection failed
          cause: EventSource error

    Side effects: none
    Idempotent: no
    """
    ...

# ── REQUIRED EXPORTS ──────────────────────────────────
# Your implementation module MUST export ALL of these names
# with EXACTLY these spellings. Tests import them by name.
# __all__ = ['EventType', 'BaseEvent', 'AgentEventPayload', 'AgentEvent', 'PactEventPayload', 'PactEvent', 'TaskEventPayload', 'TaskEvent', 'SystemEventPayload', 'SystemEvent', 'Event', 'EventBusState', 'FileWatcherState', 'WatchOptions', 'SSEFilterParams', 'PaginationParams', 'EventFilters', 'EventBusConfig', 'EventBusError', 'WatcherError', 'ParseError', 'SubscriptionError', 'SerializationError', 'MockEventBus', 'MockFileWatcher', 'createEventBus', 'emit', 'subscribe', 'unsubscribe', 'destroyEventBus', 'getFileWatcher', 'watch', 'closeFileWatcher', 'handleSSERequest', 'persistEvent', 'getEvents', 'serializeEvent', 'parseEventId', 'createEventPredicate', 'testSSEConnection']
