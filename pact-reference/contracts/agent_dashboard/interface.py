# === Agent Overview & Detail Pages (agent_dashboard) v1 ===
# Agent list page showing all agents from openclaw.json: name, status indicator (active/idle/error), current session info, assigned tasks (joined from SQLite), cumulative token usage. Agent detail page with session history, token usage over time chart (recharts line chart), assigned tasks list, and activity feed filtered to this agent. Handles missing/malformed openclaw.json with error state UI (AC2). All data fetched via lib/data/ layer. Layered architecture: Domain Types → Zod Schemas → Data Access → API Responses → Component Props → SSE Events.

# Module invariants:
#   - All data access goes through lib/data/ layer — components and API routes never read files or query SQLite directly
#   - All external input (API params, file content) is validated with Zod schemas before use
#   - No `any` types — use `unknown` + type narrowing when type is uncertain (per project standards)
#   - Data functions return Result<T, DataError> — never throw exceptions for expected error conditions
#   - All timestamps are ISO 8601 UTC strings (no Date objects across serialization boundaries)
#   - AgentId is a branded string type — plain strings must be cast through a validation function
#   - openclaw.json parse failures produce graceful error state UI (AC2), never crash the page
#   - Token usage total_tokens always equals input_tokens + output_tokens
#   - Session list is always sorted by started_at descending (newest first)
#   - Tasks are sorted by priority (critical > high > medium > low) then created_at descending
#   - SSE events are namespaced with 'agent:' prefix for the agent domain
#   - API routes return typed JSON with Content-Type: application/json
#   - Client components ('use client') receive serialized data as props — never fetch data themselves on initial render
#   - Server components are the default — 'use client' only for interactivity (charts, SSE subscription, event handlers)
#   - Empty data states (no agents, no sessions, no tasks) are valid success cases, not errors
#   - Malformed individual session files are skipped with a warning log, not treated as fatal errors

AgentId = primitive  # Branded string type for agent identifiers. Runtime: string. Compile-time: branded via `string & { readonly __brand: 'AgentId' }`. Must be non-empty, lowercase alphanumeric with hyphens only.

class AgentStatusKind(Enum):
    """Discriminant for the AgentStatus union. Determines which contextual fields are present."""
    active = "active"
    idle = "idle"
    error = "error"

class AgentStatusActive:
    """Status payload when agent is actively running a session."""
    kind: str                                # required, custom(value === 'active'), Literal 'active'
    current_session_id: str                  # required, ID of the currently running session.
    started_at: str                          # required, regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$), ISO 8601 timestamp when current session started.
    current_task_description: str = None     # optional, Human-readable description of what the agent is currently working on.

class AgentStatusIdle:
    """Status payload when agent is idle (not running)."""
    kind: str                                # required, custom(value === 'idle'), Literal 'idle'
    last_active_at: str = None               # optional, ISO 8601 timestamp of last activity. Empty string if never active.

class AgentStatusError:
    """Status payload when agent is in an error state."""
    kind: str                                # required, custom(value === 'error'), Literal 'error'
    error_message: str                       # required, Human-readable error description.
    error_code: str = unknown                # optional, Machine-readable error code, e.g. 'session_crash', 'config_invalid'.
    occurred_at: str                         # required, regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$), ISO 8601 timestamp when error occurred.

AgentStatus = AgentStatusActive | AgentStatusIdle | AgentStatusError

class TokenUsageSummary:
    """Cumulative token usage counters for an agent."""
    total_input_tokens: int                  # required, range(>=0), Total prompt/input tokens consumed across all sessions.
    total_output_tokens: int                 # required, range(>=0), Total completion/output tokens consumed across all sessions.
    total_tokens: int                        # required, range(>=0), Sum of input + output tokens.
    estimated_cost_usd: float                # required, range(>=0.0), Estimated cumulative cost in USD based on model pricing.
    session_count: int                       # required, range(>=0), Number of sessions contributing to this summary.

class Agent:
    """Summary representation of an agent for the list page. Composed from openclaw.json (name, model, status) joined with SQLite (tasks, tokens)."""
    id: AgentId                              # required, Unique agent identifier (branded string).
    name: str                                # required, Human-readable agent name from openclaw.json.
    model: str                               # required, LLM model identifier, e.g. 'claude-sonnet-4-20250514'.
    status: AgentStatus                      # required, Current agent status as discriminated union.
    token_usage: TokenUsageSummary           # required, Cumulative token usage summary.
    assigned_task_count: int                 # required, range(>=0), Number of tasks currently assigned to this agent (from SQLite).
    tags: list = []                          # optional, Optional tags/labels from openclaw config.

class AgentSession:
    """A single agent work session with timing and token data."""
    session_id: str                          # required, Unique session identifier.
    agent_id: AgentId                        # required, Agent that ran this session.
    started_at: str                          # required, regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$), ISO 8601 start timestamp.
    ended_at: str = None                     # optional, ISO 8601 end timestamp. Empty string if session is still active.
    duration_seconds: int = 0                # optional, range(>=0), Session duration in seconds. 0 if still active.
    input_tokens: int                        # required, range(>=0), Input tokens consumed in this session.
    output_tokens: int                       # required, range(>=0), Output tokens consumed in this session.
    total_tokens: int                        # required, range(>=0), Total tokens in this session.
    cost_usd: float                          # required, range(>=0.0), Estimated cost for this session in USD.
    exit_status: SessionExitStatus = running # optional, How the session ended.
    task_description: str = None             # optional, What was being worked on.

class SessionExitStatus(Enum):
    """How an agent session terminated."""
    running = "running"
    completed = "completed"
    error = "error"
    timeout = "timeout"
    cancelled = "cancelled"

class AgentTask:
    """A task assigned to an agent, stored in SQLite."""
    task_id: str                             # required, Unique task identifier.
    agent_id: AgentId                        # required, Assigned agent.
    title: str                               # required, Task title.
    description: str = None                  # optional, Task description.
    status: TaskStatus                       # required, Current task status.
    priority: TaskPriority                   # required, Task priority level.
    created_at: str                          # required, ISO 8601 creation timestamp.
    updated_at: str                          # required, ISO 8601 last update timestamp.
    completed_at: str = None                 # optional, ISO 8601 completion timestamp. Empty if not completed.
    project_id: str = None                   # optional, Associated project identifier.

class TaskStatus(Enum):
    """Task lifecycle status."""
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class TaskPriority(Enum):
    """Task priority levels."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class TokenUsageDataPoint:
    """A single data point for the recharts token usage line chart. Keyed by time bucket."""
    timestamp: str                           # required, ISO 8601 timestamp representing the start of the time bucket.
    input_tokens: int                        # required, range(>=0), Input tokens consumed in this bucket.
    output_tokens: int                       # required, range(>=0), Output tokens consumed in this bucket.
    total_tokens: int                        # required, range(>=0), Total tokens in this bucket.
    cost_usd: float                          # required, range(>=0.0), Estimated cost in this bucket.
    session_count: int                       # required, range(>=0), Number of sessions in this bucket.

class AgentDetail:
    """Full agent detail for the detail page. Extends Agent with session history, tasks, and chart data."""
    agent: Agent                             # required, Core agent summary data.
    recent_sessions: list                    # required, Most recent sessions for this agent, ordered newest-first.
    assigned_tasks: list                     # required, Tasks currently assigned to this agent.
    token_usage_timeline: list               # required, Time-series token usage data for chart rendering.
    total_sessions: int                      # required, range(>=0), Total session count for pagination.

class TimeRange(Enum):
    """Predefined time range for filtering token usage data."""
    1h = "1h"
    6h = "6h"
    24h = "24h"
    7d = "7d"
    30d = "30d"
    all = "all"

class PaginationParams:
    """Pagination parameters for list queries."""
    page: int                                # required, range(>=1), 1-based page number.
    page_size: int                           # required, range(>=1 && <=100), Items per page.

class PaginatedResult:
    """Generic paginated result wrapper."""
    items: list                              # required, The items for the current page.
    total_count: int                         # required, range(>=0), Total number of items across all pages.
    page: int                                # required, Current page number.
    page_size: int                           # required, Items per page.
    has_next: bool                           # required, Whether there is a next page.
    has_previous: bool                       # required, Whether there is a previous page.

class DataErrorKind(Enum):
    """Discriminant for DataError union. Categorizes data access failures."""
    file_not_found = "file_not_found"
    file_parse_error = "file_parse_error"
    db_error = "db_error"
    agent_not_found = "agent_not_found"
    validation_error = "validation_error"

class DataError:
    """Structured error type returned from data access layer. Part of Result<T, DataError> pattern."""
    kind: DataErrorKind                      # required, Error category discriminant.
    message: str                             # required, Human-readable error message.
    source_path: str = None                  # optional, File path or DB table that caused the error.
    details: dict = {}                       # optional, Additional structured error context (e.g., Zod issues, SQL error code).

class ResultOk:
    """Success variant of Result<T, DataError>."""
    ok: bool                                 # required, custom(value === true), Literal true.
    data: any                                # required, The success payload. Actual type depends on the function returning this Result.

class ResultErr:
    """Error variant of Result<T, DataError>."""
    ok: bool                                 # required, custom(value === false), Literal false.
    error: DataError                         # required, The structured error.

Result = ResultOk | ResultErr

class AgentRawConfig:
    """Raw agent entry as parsed from openclaw.json before domain mapping. Validated via Zod AgentRawSchema."""
    id: str                                  # required, regex(^[a-z0-9-]+$), Agent identifier from config.
    name: str                                # required, length(>=1 && <=128), Display name.
    model: str                               # required, Model identifier string.
    status: str                              # required, Raw status string from config. Mapped to AgentStatus union.
    current_session: dict = {}               # optional, Raw current session data if active. May be null/missing.
    tags: list = []                          # optional, Optional tags.
    error: dict = {}                         # optional, Raw error data if status is error.

class OpenClawConfig:
    """Top-level openclaw.json structure. Validated via Zod OpenClawConfigSchema."""
    version: str = 1                         # optional, Config file version.
    agents: list                             # required, List of agent configurations.
    base_path: str = None                    # optional, Base directory for OpenClaw data.
    sessions_dir: str = sessions             # optional, Directory containing session data files.

class AgentListResponse:
    """API response shape for GET /api/agents. Wire format."""
    agents: list                             # required, List of all agents.
    total_count: int                         # required, Total number of agents.
    fetched_at: str                          # required, ISO 8601 timestamp when data was fetched. Used for cache invalidation.

class AgentDetailResponse:
    """API response shape for GET /api/agents/[agentId]. Wire format."""
    agent: AgentDetail                       # required, Full agent detail.
    fetched_at: str                          # required, ISO 8601 timestamp when data was fetched.

class AgentErrorResponse:
    """API error response shape for agent endpoints."""
    error: str                               # required, Error type identifier.
    message: str                             # required, Human-readable error message.
    details: dict = {}                       # optional, Additional structured error info.
    status_code: int                         # required, range(>=400 && <=599), HTTP status code.

class AgentCardProps:
    """Props for the AgentCard component displayed in the agent list. Server component."""
    agent: Agent                             # required, Agent summary data to render.

class AgentStatusBadgeProps:
    """Props for the AgentStatusBadge component. Client component for animated indicators."""
    status: AgentStatus                      # required, Agent status to render as badge.
    size: str = md                           # optional, custom(['sm', 'md', 'lg'].includes(value)), Badge size variant.

class TokenUsageChartProps:
    """Props for the TokenUsageChart recharts LineChart component. Client component ('use client')."""
    data: list                               # required, Time-series data points for the chart.
    time_range: TimeRange                    # required, Currently selected time range for display.
    on_time_range_change: str = None         # optional, Callback function name/ref for time range changes. Typed as (range: TimeRange) => void at runtime.
    height: int = 300                        # optional, range(>=100 && <=800), Chart height in pixels.
    show_cost_axis: bool = true              # optional, Whether to show the secondary cost USD axis.

class AgentActivityFeedProps:
    """Props for the AgentActivityFeed component. Client component for SSE-driven live updates."""
    agent_id: AgentId                        # required, Agent to filter activity events for.
    initial_events: list                     # required, Pre-loaded activity events for SSR.
    max_visible: int = 50                    # optional, range(>=10 && <=500), Max events to display before scrolling.

class AgentActivityEvent:
    """A single activity event for the agent activity feed."""
    event_id: str                            # required, Unique event identifier.
    agent_id: AgentId                        # required, Agent this event belongs to.
    event_type: str                          # required, Event type string, e.g. 'session_started', 'task_completed'.
    timestamp: str                           # required, ISO 8601 event timestamp.
    summary: str                             # required, Human-readable event summary.
    metadata: dict = {}                      # optional, Event-specific metadata.

class AgentSessionListProps:
    """Props for the AgentSessionList component on the detail page."""
    sessions: list                           # required, Session list to display.
    total_count: int                         # required, Total sessions for pagination.
    current_page: int                        # required, Current page number.
    page_size: int                           # required, Items per page.

class AgentTaskListProps:
    """Props for the AgentTaskList component on the detail page."""
    tasks: list                              # required, Tasks assigned to this agent.
    agent_id: AgentId                        # required, Agent these tasks belong to.

class SSEAgentStatusChanged:
    """SSE event: agent:status-changed. Emitted when an agent's status transitions."""
    type: str                                # required, custom(value === 'agent:status-changed'), Literal 'agent:status-changed'.
    agent_id: AgentId                        # required, Agent whose status changed.
    previous_status: AgentStatusKind         # required, Previous status kind.
    new_status: AgentStatus                  # required, New full status object.
    timestamp: str                           # required, ISO 8601 timestamp of the change.

class SSEAgentSessionStarted:
    """SSE event: agent:session-started. Emitted when a new agent session begins."""
    type: str                                # required, custom(value === 'agent:session-started'), Literal 'agent:session-started'.
    agent_id: AgentId                        # required, Agent that started the session.
    session_id: str                          # required, New session identifier.
    started_at: str                          # required, ISO 8601 session start timestamp.
    task_description: str = None             # optional, What the session is working on.

class SSEAgentSessionEnded:
    """SSE event: agent:session-ended. Emitted when an agent session completes or fails."""
    type: str                                # required, custom(value === 'agent:session-ended'), Literal 'agent:session-ended'.
    agent_id: AgentId                        # required, Agent whose session ended.
    session_id: str                          # required, Ended session identifier.
    ended_at: str                            # required, ISO 8601 session end timestamp.
    exit_status: SessionExitStatus           # required, How the session ended.
    token_usage: TokenUsageSummary           # required, Token usage for the ended session.

SSEAgentEvent = SSEAgentStatusChanged | SSEAgentSessionStarted | SSEAgentSessionEnded

class AgentListErrorStateProps:
    """Props for the error state UI shown when openclaw.json is missing or malformed (AC2)."""
    error_kind: DataErrorKind                # required, The kind of error that occurred.
    error_message: str                       # required, Human-readable error for display.
    config_path: str = None                  # optional, The path that was attempted for openclaw.json.
    on_retry: str = None                     # optional, Callback ref for retry action. Typed as () => void at runtime.

def parseOpenClawConfig(
    config_path: str,          # length(>=1)
) -> Result:
    """
    Parse and validate openclaw.json from the filesystem using Zod OpenClawConfigSchema.safeParse(). Returns the parsed config or a structured DataError. Located in lib/openclaw/schemas.ts.

    Preconditions:
      - config_path is an absolute filesystem path

    Postconditions:
      - On success (ok=true), data is a valid OpenClawConfig
      - On file_not_found error, source_path matches config_path
      - On file_parse_error, details contains Zod validation issues
      - Never throws — all errors are returned as ResultErr

    Errors:
      - file_not_found (DataError): openclaw.json does not exist at config_path
          kind: file_not_found
      - file_read_error (DataError): File exists but cannot be read (permissions, IO error)
          kind: file_parse_error
      - invalid_json (DataError): File content is not valid JSON
          kind: file_parse_error
      - schema_validation_failed (DataError): JSON is valid but does not match OpenClawConfigSchema
          kind: validation_error

    Side effects: none
    Idempotent: yes
    """
    ...

def mapRawAgentToDomain(
    raw: AgentRawConfig,
    token_usage: TokenUsageSummary,
    assigned_task_count: int,  # range(>=0)
) -> Agent:
    """
    Transform a raw AgentRawConfig (from Zod parse) into the domain Agent type. Maps raw status strings to the AgentStatus discriminated union. Pure function in lib/openclaw/schemas.ts.

    Preconditions:
      - raw has passed Zod schema validation

    Postconditions:
      - Returned Agent.id is a branded AgentId equal to raw.id
      - Agent.status.kind matches raw.status (mapped to valid AgentStatusKind)
      - Agent.token_usage === token_usage parameter
      - Agent.assigned_task_count === assigned_task_count parameter

    Errors:
      - unknown_status (DataError): raw.status is not 'active', 'idle', or 'error'
          kind: validation_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getAgents() -> Result:
    """
    Fetch all agents from openclaw.json, join with SQLite for task counts and token usage. Returns the full agent list. Located in lib/data/agents.ts.

    Preconditions:
      - OpenClaw config path is configured in environment or lib/openclaw/config

    Postconditions:
      - On success, data is list of Agent objects sorted by name alphabetically
      - Each Agent has accurate assigned_task_count from SQLite
      - Each Agent has accurate token_usage from session data
      - On file_not_found or parse error, returns ResultErr (never throws)

    Errors:
      - config_not_found (DataError): openclaw.json does not exist
          kind: file_not_found
      - config_parse_error (DataError): openclaw.json is malformed or invalid
          kind: file_parse_error
      - db_error (DataError): SQLite query for tasks or token usage fails
          kind: db_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getAgentById(
    agent_id: AgentId,         # regex(^[a-z0-9-]+$)
) -> Result:
    """
    Fetch a single agent by ID. Returns Agent summary or agent_not_found error. Located in lib/data/agents.ts.

    Preconditions:
      - agent_id is a valid non-empty branded AgentId string

    Postconditions:
      - On success, data is a single Agent matching the requested ID
      - On agent_not_found, error message includes the requested agent_id

    Errors:
      - config_not_found (DataError): openclaw.json does not exist
          kind: file_not_found
      - config_parse_error (DataError): openclaw.json is malformed
          kind: file_parse_error
      - agent_not_found (DataError): No agent with the given ID exists in openclaw.json
          kind: agent_not_found
      - db_error (DataError): SQLite query fails
          kind: db_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getAgentSessions(
    agent_id: AgentId,         # regex(^[a-z0-9-]+$)
    pagination: PaginationParams,
) -> Result:
    """
    Fetch paginated session history for a specific agent. Reads session data from OpenClaw session files. Located in lib/data/agents.ts.

    Preconditions:
      - agent_id is a valid non-empty branded AgentId string
      - pagination.page >= 1
      - pagination.page_size >= 1 && pagination.page_size <= 100

    Postconditions:
      - On success, data is PaginatedResult with items of type AgentSession
      - Sessions are ordered by started_at descending (newest first)
      - total_count reflects all sessions for this agent, not just current page
      - has_next is true iff (page * page_size) < total_count

    Errors:
      - agent_not_found (DataError): No agent with the given ID exists
          kind: agent_not_found
      - sessions_dir_missing (DataError): Sessions directory does not exist
          kind: file_not_found
      - session_parse_error (DataError): One or more session files are malformed (skipped gracefully, logged)
          kind: file_parse_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getAgentTokenUsage(
    agent_id: AgentId,         # regex(^[a-z0-9-]+$)
    time_range: TimeRange,
) -> Result:
    """
    Fetch time-bucketed token usage data for an agent over a time range. Returns recharts-ready data points. Located in lib/data/agents.ts.

    Preconditions:
      - agent_id is a valid non-empty branded AgentId string
      - time_range is a valid TimeRange variant

    Postconditions:
      - On success, data is list of TokenUsageDataPoint ordered by timestamp ascending
      - Data points are evenly bucketed: 1h→1min, 6h→5min, 24h→30min, 7d→6h, 30d→1d, all→1d
      - Each data point's total_tokens === input_tokens + output_tokens
      - Empty buckets are included with zero values (no gaps in timeline)

    Errors:
      - agent_not_found (DataError): No agent with the given ID exists
          kind: agent_not_found
      - session_data_error (DataError): Cannot read or parse session data for token aggregation
          kind: file_parse_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getAgentTasks(
    agent_id: AgentId,         # regex(^[a-z0-9-]+$)
) -> Result:
    """
    Fetch all tasks assigned to a specific agent from SQLite. Located in lib/data/agents.ts.

    Preconditions:
      - agent_id is a valid non-empty branded AgentId string

    Postconditions:
      - On success, data is list of AgentTask where each task.agent_id === agent_id
      - Tasks are ordered by priority (critical > high > medium > low), then by created_at descending
      - Returns empty list (not error) if agent exists but has no tasks

    Errors:
      - db_error (DataError): SQLite query fails
          kind: db_error
      - agent_not_found (DataError): Agent ID does not exist in openclaw.json (validated before DB query)
          kind: agent_not_found

    Side effects: none
    Idempotent: yes
    """
    ...

def getAgentDetail(
    agent_id: AgentId,         # regex(^[a-z0-9-]+$)
    session_pagination: PaginationParams = None,
    token_time_range: TimeRange = 7d,
) -> Result:
    """
    Compose full agent detail by calling getAgentById, getAgentSessions, getAgentTokenUsage, and getAgentTasks. Returns AgentDetail or first encountered error. Located in lib/data/agents.ts.

    Preconditions:
      - agent_id is a valid non-empty branded AgentId string

    Postconditions:
      - On success, data is an AgentDetail with all sub-fields populated
      - agent field matches getAgentById result
      - recent_sessions matches getAgentSessions result items
      - token_usage_timeline matches getAgentTokenUsage result
      - assigned_tasks matches getAgentTasks result
      - If any sub-query fails, entire call returns the first error (fail-fast)

    Errors:
      - agent_not_found (DataError): Agent does not exist in openclaw.json
          kind: agent_not_found
      - config_not_found (DataError): openclaw.json does not exist
          kind: file_not_found
      - config_parse_error (DataError): openclaw.json is malformed
          kind: file_parse_error
      - session_data_error (DataError): Session files cannot be read
          kind: file_parse_error
      - db_error (DataError): SQLite query fails
          kind: db_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getAgentActivityEvents(
    agent_id: AgentId,         # regex(^[a-z0-9-]+$)
    limit: int,                # range(>=1 && <=500)
) -> Result:
    """
    Fetch recent activity events for an agent from session data and task history. Used for initial SSR of the activity feed before SSE takes over. Located in lib/data/agents.ts.

    Preconditions:
      - agent_id is a valid non-empty branded AgentId string

    Postconditions:
      - On success, data is list of AgentActivityEvent ordered by timestamp descending
      - List length <= limit
      - Each event.agent_id === agent_id

    Errors:
      - agent_not_found (DataError): Agent does not exist
          kind: agent_not_found
      - data_error (DataError): Session files or SQLite query fails
          kind: file_parse_error

    Side effects: none
    Idempotent: yes
    """
    ...

def handleGetAgents() -> AgentListResponse:
    """
    API route handler for GET /api/agents. Calls getAgents(), serializes to AgentListResponse or AgentErrorResponse. Located in app/api/agents/route.ts.

    Postconditions:
      - Returns HTTP 200 with AgentListResponse on success
      - Returns HTTP 404 with AgentErrorResponse when openclaw.json not found
      - Returns HTTP 500 with AgentErrorResponse on parse or DB errors
      - Response Content-Type is application/json
      - fetched_at is set to current ISO 8601 timestamp

    Errors:
      - config_missing (AgentErrorResponse): openclaw.json not found
          status_code: 404
      - config_invalid (AgentErrorResponse): openclaw.json malformed
          status_code: 500
      - internal_error (AgentErrorResponse): Unexpected error in data layer
          status_code: 500

    Side effects: none
    Idempotent: yes
    """
    ...

def handleGetAgentById(
    agent_id: str,             # regex(^[a-z0-9-]+$), length(>=1 && <=64)
    time_range: str = 7d,
    sessions_page: int = 1,    # range(>=1)
    sessions_page_size: int = 20, # range(>=1 && <=100)
) -> AgentDetailResponse:
    """
    API route handler for GET /api/agents/[agentId]. Validates agentId param with Zod, calls getAgentDetail(), serializes to AgentDetailResponse or AgentErrorResponse. Located in app/api/agents/[agentId]/route.ts.

    Postconditions:
      - Returns HTTP 200 with AgentDetailResponse on success
      - Returns HTTP 400 with AgentErrorResponse on invalid agentId or query params
      - Returns HTTP 404 with AgentErrorResponse when agent not found
      - Returns HTTP 500 with AgentErrorResponse on internal errors
      - Response Content-Type is application/json

    Errors:
      - invalid_agent_id (AgentErrorResponse): agentId path param fails Zod validation
          status_code: 400
      - invalid_query_params (AgentErrorResponse): Query params fail Zod validation
          status_code: 400
      - agent_not_found (AgentErrorResponse): No agent with given ID exists
          status_code: 404
      - config_missing (AgentErrorResponse): openclaw.json not found
          status_code: 404
      - internal_error (AgentErrorResponse): Data layer error
          status_code: 500

    Side effects: none
    Idempotent: yes
    """
    ...

def emitAgentSSEEvent(
    event: SSEAgentEvent,
) -> None:
    """
    Emit an agent-related SSE event to the event bus for distribution to connected clients. Located in lib/sse/agent-events.ts. Called by file watchers when openclaw.json or session files change.

    Preconditions:
      - event is a valid SSEAgentEvent union member
      - SSE event bus is initialized

    Postconditions:
      - Event is enqueued on the SSE event bus for all subscribed clients
      - Clients with agent_id filter only receive events matching their filter
      - Event is serialized as JSON in the SSE data field

    Errors:
      - event_bus_not_initialized (DataError): SSE event bus has not been started
          kind: db_error
      - serialization_error (DataError): Event cannot be serialized to JSON
          kind: validation_error

    Side effects: none
    Idempotent: no
    """
    ...

# ── REQUIRED EXPORTS ──────────────────────────────────
# Your implementation module MUST export ALL of these names
# with EXACTLY these spellings. Tests import them by name.
# __all__ = ['AgentStatusKind', 'AgentStatusActive', 'AgentStatusIdle', 'AgentStatusError', 'AgentStatus', 'TokenUsageSummary', 'Agent', 'AgentSession', 'SessionExitStatus', 'AgentTask', 'TaskStatus', 'TaskPriority', 'TokenUsageDataPoint', 'AgentDetail', 'TimeRange', 'PaginationParams', 'PaginatedResult', 'DataErrorKind', 'DataError', 'ResultOk', 'ResultErr', 'Result', 'AgentRawConfig', 'OpenClawConfig', 'AgentListResponse', 'AgentDetailResponse', 'AgentErrorResponse', 'AgentCardProps', 'AgentStatusBadgeProps', 'TokenUsageChartProps', 'AgentActivityFeedProps', 'AgentActivityEvent', 'AgentSessionListProps', 'AgentTaskListProps', 'SSEAgentStatusChanged', 'SSEAgentSessionStarted', 'SSEAgentSessionEnded', 'SSEAgentEvent', 'AgentListErrorStateProps', 'parseOpenClawConfig', 'mapRawAgentToDomain', 'getAgents', 'getAgentById', 'getAgentSessions', 'getAgentTokenUsage', 'getAgentTasks', 'getAgentDetail', 'getAgentActivityEvents', 'handleGetAgents', 'handleGetAgentById', 'emitAgentSSEEvent']
