# === Activity Feed & Cost Tracking Pages (activity_cost_pages) v1 ===
# Activity feed full page: chronological event list auto-updating via SSE (useEventSource hook), filterable by agent/project/event type (AC7). Cost & Token dashboard page: per-project and per-agent cost breakdown bar charts, token usage over time line charts (recharts), budget alert configuration stored in SQLite. Gracefully shows 'no data available' placeholder UI when token/cost data is missing from filesystem (AC8). Overview/home dashboard page that aggregates: agent count + status summary cards, active projects count, PACT health snapshot, last 10 activity events, cost burn rate. Uses Zod-first approach where Zod schemas are single source of truth with TypeScript types inferred via z.infer. All timestamps ISO 8601 strings. All monetary values as integer microdollars (1 USD = 1,000,000 microdollars) formatted to dollars only at UI presentation layer.

# Module invariants:
#   - All monetary values are stored and transmitted as integer microdollars (1 USD = 1,000,000 microdollars); conversion to display dollars happens only in UI presentation layer or in chart transform functions
#   - All timestamps are ISO 8601 strings with timezone information
#   - All data access functions return DataResult — components never access filesystem or SQLite directly
#   - Components never import from OpenClaw or PACT libraries directly; all integration is via filesystem reads and CLI invocations through the data access layer
#   - ActivityEvent IDs are UUID v4 and globally unique; used for SSE deduplication via lastEventId
#   - The SSE endpoint at /api/events is the single multiplexed stream for all event types; no per-type SSE endpoints
#   - Budget alerts are persisted exclusively in SQLite (dashboard-specific data); agent/project/cost data is read from filesystem (OpenClaw/PACT data)
#   - Zod schemas are the single source of truth for all type definitions; TypeScript types are inferred via z.infer<typeof schema>
#   - All external input (API params, file contents, CLI output) is validated through Zod schemas before use
#   - DataResult with status='empty' triggers 'no data available' placeholder UI (AC8); it is not treated as an error
#   - SSE heartbeat events are emitted every 30 seconds to keep connections alive
#   - BudgetAlert evaluation includes debounce logic: an alert is not re-triggered if last_triggered_at is within the same evaluation period
#   - DashboardOverviewResponse sections fail independently: one section's error does not prevent other sections from rendering
#   - Files in this component respect the 250-line limit; types are split across lib/types/activity.ts, cost.ts, budget.ts, dashboard.ts, common.ts, sse.ts with a barrel index.ts

class ActivityEventType(Enum):
    """Dot-notation taxonomy of all activity event types, used as discriminant for ActivityEvent union."""
    agent.started = "agent.started"
    agent.stopped = "agent.stopped"
    agent.error = "agent.error"
    agent.idle = "agent.idle"
    task.created = "task.created"
    task.assigned = "task.assigned"
    task.completed = "task.completed"
    task.failed = "task.failed"
    task.cancelled = "task.cancelled"
    project.created = "project.created"
    project.updated = "project.updated"
    project.archived = "project.archived"
    pact.approval_requested = "pact.approval_requested"
    pact.approved = "pact.approved"
    pact.rejected = "pact.rejected"
    pact.timed_out = "pact.timed_out"
    cost.threshold_crossed = "cost.threshold_crossed"
    cost.budget_exceeded = "cost.budget_exceeded"
    system.sse_connected = "system.sse_connected"
    system.sse_reconnected = "system.sse_reconnected"

class DataResultStatus(Enum):
    """Status discriminant for DataResult<T> wrapper. 'ok' = data present, 'empty' = no data found (graceful empty state for AC8), 'error' = retrieval failed."""
    ok = "ok"
    empty = "empty"
    error = "error"

class DataResultOk:
    """DataResult variant when data is successfully retrieved."""
    status: DataResultStatus                 # required, custom(status === 'ok'), Always 'ok'.
    data: any                                # required, The successfully retrieved data payload. Generic T in implementation; typed per usage site via Zod schema inference.

class DataResultEmpty:
    """DataResult variant when no data is available (e.g., filesystem cost files missing). Used to trigger 'no data available' placeholder UI (AC8)."""
    status: DataResultStatus                 # required, custom(status === 'empty'), Always 'empty'.
    reason: str                              # required, Human-readable reason why data is empty, e.g. 'No cost data files found for project X'.

class DataResultError:
    """DataResult variant when data retrieval failed due to an error."""
    status: DataResultStatus                 # required, custom(status === 'error'), Always 'error'.
    error_code: str                          # required, Machine-readable error code, e.g. 'FILE_READ_FAILED', 'PARSE_ERROR', 'DB_QUERY_FAILED'.
    error_message: str                       # required, Human-readable error description.

DataResult = DataResultOk | DataResultEmpty | DataResultError

class ActivityEvent:
    """A single activity event in the chronological feed. Parsed from filesystem event logs via Zod schema. IDs are UUIDs for SSE deduplication."""
    id: str                                  # required, regex(^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$), Unique event ID (UUID v4). Used for SSE deduplication via lastEventId.
    type: ActivityEventType                  # required, Dot-notation event type, used as discriminant for event-specific payloads.
    timestamp: str                           # required, regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$), ISO 8601 timestamp of when the event occurred.
    agent_id: str = None                     # optional, ID of the agent that generated this event, if applicable.
    project_id: str = None                   # optional, ID of the project this event relates to, if applicable.
    task_id: str = None                      # optional, ID of the task this event relates to, if applicable.
    summary: str                             # required, Human-readable one-line summary of the event.
    details: dict = None                     # optional, Event-type-specific structured details. Schema varies by event type; validated per-type via Zod discriminated union.
    severity: EventSeverity = info           # optional, Event severity level for visual treatment in the feed.

class EventSeverity(Enum):
    """Severity level for activity events, controls visual treatment in the UI feed."""
    info = "info"
    warning = "warning"
    error = "error"
    success = "success"

class ActivityFilter:
    """First-class filter object for the activity feed. Used both in API query params (validated via Zod) and in SSE subscription filters."""
    agent_ids: StringList = None             # optional, Filter to events from these agent IDs. Empty or omitted = all agents.
    project_ids: StringList = None           # optional, Filter to events for these project IDs. Empty or omitted = all projects.
    event_types: ActivityEventTypeList = None # optional, Filter to these event types. Empty or omitted = all types.
    severity: EventSeverityList = None       # optional, Filter by severity levels. Empty or omitted = all severities.
    since: str = None                        # optional, Only events after this ISO 8601 timestamp.
    until: str = None                        # optional, Only events before this ISO 8601 timestamp.

StringList = list[str]
# A list of strings.

ActivityEventTypeList = list[ActivityEventType]
# A list of ActivityEventType enum values for filtering.

EventSeverityList = list[EventSeverity]
# A list of EventSeverity enum values for filtering.

class CursorPagination:
    """Cursor-based pagination parameters. Cursor is the event ID of the last item in the previous page."""
    cursor: str = None                       # optional, Event ID cursor for pagination. Empty string or omitted = start from most recent.
    limit: int = 50                          # optional, range(1..200), Maximum number of items to return per page.

ActivityEventList = list[ActivityEvent]
# Ordered list of activity events (most recent first).

class ActivityFeedResponse:
    """Cursor-paginated activity feed API response."""
    events: ActivityEventList                # required, Activity events for the current page, ordered most recent first.
    next_cursor: str = None                  # optional, Cursor for the next page. Empty string if no more pages.
    has_more: bool                           # required, Whether there are more events beyond this page.
    total_count: int = None                  # optional, Total count of events matching the filter, if available. May be omitted for performance on large datasets.

class CostRecord:
    """A single per-invocation cost record. Read from filesystem cost logs. All monetary values in integer microdollars (1 USD = 1,000,000 microdollars)."""
    id: str                                  # required, Unique cost record ID.
    timestamp: str                           # required, regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$), ISO 8601 timestamp of the invocation.
    agent_id: str                            # required, Agent that incurred this cost.
    project_id: str                          # required, Project the cost is attributed to.
    model: str                               # required, LLM model identifier, e.g. 'claude-sonnet-4-20250514'.
    input_tokens: int                        # required, range(0..999999999), Number of input/prompt tokens.
    output_tokens: int                       # required, range(0..999999999), Number of output/completion tokens.
    cost_microdollars: int                   # required, range(0..999999999999), Cost in microdollars (1 USD = 1,000,000). Integer to avoid floating-point precision issues.
    session_id: str = None                   # optional, OpenClaw session ID, if available.
    task_id: str = None                      # optional, Task ID this invocation was part of, if available.

class TokenUsage:
    """Aggregated token usage for a time period. Used in token usage charts."""
    period_start: str                        # required, ISO 8601 timestamp for start of this aggregation period.
    period_end: str                          # required, ISO 8601 timestamp for end of this aggregation period.
    input_tokens: int                        # required, range(0..999999999999), Total input tokens in this period.
    output_tokens: int                       # required, range(0..999999999999), Total output tokens in this period.
    total_tokens: int                        # required, range(0..999999999999), Sum of input + output tokens.
    invocation_count: int                    # required, range(0..999999999), Number of LLM invocations in this period.

class BudgetAlert:
    """Budget alert configuration stored in SQLite. Defines a spending threshold that triggers a notification when crossed."""
    id: str                                  # required, regex(^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$), Unique alert ID (UUID v4).
    name: str                                # required, length(1..200), User-defined alert name.
    scope_type: BudgetAlertScopeType         # required, Whether this alert applies to a specific project, agent, or globally.
    scope_id: str = None                     # optional, The project_id or agent_id this alert scopes to. Empty for global scope.
    threshold_microdollars: int              # required, range(1..999999999999), Spending threshold in microdollars. Alert fires when cumulative cost crosses this value.
    period: BudgetAlertPeriod                # required, Time period over which spending is aggregated for threshold comparison.
    enabled: bool                            # required, Whether this alert is currently active.
    last_triggered_at: str = None            # optional, ISO 8601 timestamp of when this alert last fired. Used for debounce to avoid repeated notifications.
    created_at: str                          # required, ISO 8601 timestamp of alert creation.
    updated_at: str                          # required, ISO 8601 timestamp of last alert modification.

class BudgetAlertScopeType(Enum):
    """Scope type for budget alerts."""
    global = "global"
    project = "project"
    agent = "agent"

class BudgetAlertPeriod(Enum):
    """Time period over which budget alert thresholds are evaluated."""
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    total = "total"

class BudgetAlertCreateInput:
    """Input for creating a new budget alert. Validated via Zod schema."""
    name: str                                # required, length(1..200), User-defined alert name.
    scope_type: BudgetAlertScopeType         # required, Scope of the alert.
    scope_id: str = None                     # optional, The project_id or agent_id. Required when scope_type is 'project' or 'agent'.
    threshold_microdollars: int              # required, range(1..999999999999), Spending threshold in microdollars.
    period: BudgetAlertPeriod                # required, Aggregation period for threshold comparison.
    enabled: bool = true                     # optional, Whether the alert is enabled on creation.

class BudgetAlertUpdateInput:
    """Input for updating an existing budget alert. All fields optional (partial update)."""
    name: str = None                         # optional, Updated alert name.
    threshold_microdollars: int = None       # optional, range(1..999999999999), Updated threshold.
    period: BudgetAlertPeriod = None         # optional, Updated period.
    enabled: bool = None                     # optional, Updated enabled state.

BudgetAlertList = list[BudgetAlert]
# List of budget alert configurations.

class BudgetAlertCrudResponse:
    """Standard CRUD response for budget alert operations."""
    success: bool                            # required, Whether the operation succeeded.
    alert: BudgetAlert = None                # optional, The created/updated/retrieved alert. Present on success for create/update/get operations.
    alerts: BudgetAlertList = None           # optional, List of alerts. Present on success for list operations.
    deleted_id: str = None                   # optional, ID of the deleted alert. Present on success for delete operations.
    error: str = None                        # optional, Error message on failure.

class CostBreakdownEntry:
    """A single entry in a cost breakdown (by project or by agent)."""
    entity_id: str                           # required, The project_id or agent_id.
    entity_name: str                         # required, Human-readable name of the project or agent.
    total_cost_microdollars: int             # required, range(0..999999999999), Total cost in microdollars for this entity.
    total_input_tokens: int                  # required, Total input tokens.
    total_output_tokens: int                 # required, Total output tokens.
    invocation_count: int                    # required, Total LLM invocations.

CostBreakdownList = list[CostBreakdownEntry]
# List of cost breakdown entries.

class TimeBucketGranularity(Enum):
    """Granularity for time-bucketed data series."""
    hour = "hour"
    day = "day"
    week = "week"
    month = "month"

class CostChartDataPoint:
    """Flat object shaped for direct recharts consumption in cost bar charts."""
    label: str                               # required, X-axis label (entity name for breakdown charts, time label for time series).
    cost_dollars: float                      # required, Cost in dollars (converted from microdollars for display). This is the sole exception where dollar formatting occurs in the data transform layer rather than UI.
    cost_microdollars: int                   # required, Cost in microdollars (original value for tooltip precision).

CostChartDataPointList = list[CostChartDataPoint]
# List of cost chart data points for recharts.

class TokenChartDataPoint:
    """Flat object shaped for direct recharts consumption in token usage line charts."""
    label: str                               # required, X-axis label (time bucket label).
    input_tokens: int                        # required, Input tokens for this data point.
    output_tokens: int                       # required, Output tokens for this data point.
    total_tokens: int                        # required, Total tokens (input + output).

TokenChartDataPointList = list[TokenChartDataPoint]
# List of token chart data points for recharts.

TokenUsageList = list[TokenUsage]
# Time-bucketed token usage series.

class CostTimeSeries:
    """Time-bucketed cost series for the cost dashboard."""
    granularity: TimeBucketGranularity       # required, Time bucket granularity.
    cost_points: CostChartDataPointList      # required, Cost data points ordered chronologically.
    token_points: TokenChartDataPointList    # required, Token usage data points ordered chronologically.

class CostDashboardResponse:
    """Aggregated cost dashboard API response. All sections independently nullable to allow partial data rendering."""
    by_project: DataResult                   # required, DataResult wrapping CostBreakdownList for per-project cost breakdown.
    by_agent: DataResult                     # required, DataResult wrapping CostBreakdownList for per-agent cost breakdown.
    time_series: DataResult                  # required, DataResult wrapping CostTimeSeries for time-bucketed cost and token series.
    total_cost_microdollars: int             # required, range(0..999999999999), Grand total cost in microdollars for the queried period.
    total_tokens: int                        # required, Grand total tokens for the queried period.
    alerts: BudgetAlertList                  # required, Active budget alerts for display in the cost dashboard.
    period_start: str                        # required, ISO 8601 start of the queried period.
    period_end: str                          # required, ISO 8601 end of the queried period.

class BurnRate:
    """Cost burn rate calculation for the dashboard overview."""
    rate_microdollars_per_hour: int          # required, range(0..999999999999), Current burn rate in microdollars per hour.
    window_hours: int                        # required, range(1..720), Time window (in hours) over which the rate was calculated.
    trend: BurnRateTrend                     # required, Direction of burn rate compared to previous window.
    trend_percentage: float                  # required, Percentage change vs previous window. Positive = increase, negative = decrease.

class BurnRateTrend(Enum):
    """Burn rate trend direction."""
    increasing = "increasing"
    decreasing = "decreasing"
    stable = "stable"

class AgentStatusSummary:
    """Agent count and status summary for the overview dashboard."""
    total: int                               # required, Total number of configured agents.
    active: int                              # required, Number of agents currently active/running.
    idle: int                                # required, Number of idle agents.
    errored: int                             # required, Number of agents in error state.
    stopped: int                             # required, Number of stopped agents.

class PactHealthSnapshot:
    """PACT system health snapshot for the overview dashboard."""
    is_healthy: bool                         # required, Whether PACT system is responding normally.
    pending_approvals: int                   # required, range(0..999999), Number of pending PACT approval requests.
    approved_last_24h: int                   # required, Number of PACT requests approved in last 24 hours.
    rejected_last_24h: int                   # required, Number of PACT requests rejected in last 24 hours.
    timed_out_last_24h: int                  # required, Number of PACT requests that timed out in last 24 hours.
    last_check_at: str                       # required, ISO 8601 timestamp of the last PACT health check.

class DashboardOverviewResponse:
    """Composite dashboard overview API response. Each section is independently wrapped in DataResult so the UI can render available sections while showing 'no data' placeholders for missing ones."""
    agent_summary: DataResult                # required, DataResult wrapping AgentStatusSummary.
    active_projects_count: DataResult        # required, DataResult wrapping int — count of active projects.
    pact_health: DataResult                  # required, DataResult wrapping PactHealthSnapshot.
    recent_activity: DataResult              # required, DataResult wrapping ActivityEventList — last 10 events.
    burn_rate: DataResult                    # required, DataResult wrapping BurnRate.
    generated_at: str                        # required, ISO 8601 timestamp when this overview was generated.

class SSEFilterParams:
    """Query parameters for subscribing to the multiplexed SSE endpoint at /api/events. All filters are optional; omitted = no filter on that dimension."""
    agent_ids: str = None                    # optional, Comma-separated agent IDs to filter on.
    project_ids: str = None                  # optional, Comma-separated project IDs to filter on.
    event_types: str = None                  # optional, Comma-separated event types to filter on.
    last_event_id: str = None                # optional, Last received event ID for reconnection. Server replays missed events since this ID.

class SSEMessage:
    """A single SSE message sent to the client. Conforms to the SSE protocol with id, event, and data fields."""
    id: str                                  # required, Event ID for lastEventId tracking. Same as ActivityEvent.id for activity events.
    event: str                               # required, SSE event type field. Uses the ActivityEventType dot-notation or 'heartbeat' for keepalive.
    data: str                                # required, JSON-serialized event payload. Parsed by client via Zod schema.
    retry: int = None                        # optional, Suggested reconnection delay in milliseconds. Only sent on initial connection.

CostRecordList = list[CostRecord]
# List of cost records.

class CostQueryParams:
    """Query parameters for cost data retrieval."""
    project_id: str = None                   # optional, Filter by project ID.
    agent_id: str = None                     # optional, Filter by agent ID.
    period_start: str = None                 # optional, ISO 8601 start of query period.
    period_end: str = None                   # optional, ISO 8601 end of query period.
    granularity: TimeBucketGranularity = day # optional, Time bucket granularity for time series data.

def listActivityEvents(
    filter: ActivityFilter = None,
    pagination: CursorPagination = None,
) -> DataResult:
    """
    Retrieves a cursor-paginated list of activity events from the filesystem event logs, filtered by the provided criteria. Events are read from OpenClaw/PACT event log files via the data access layer. Returns DataResult wrapping ActivityFeedResponse.

    Preconditions:
      - If pagination.cursor is provided, it must be a valid event ID that exists in the event log
      - If filter.since is provided, it must be a valid ISO 8601 timestamp
      - If filter.until is provided, it must be a valid ISO 8601 timestamp and >= filter.since

    Postconditions:
      - On status='ok', data contains ActivityFeedResponse with events.length <= pagination.limit
      - Events are ordered by timestamp descending (most recent first)
      - On status='ok', if has_more is true then next_cursor is a non-empty string
      - On status='empty', no event log files were found on the filesystem
      - All returned events match the provided filter criteria

    Errors:
      - INVALID_CURSOR (ValidationError): Provided cursor ID does not exist in event logs
          cursor: The invalid cursor value
      - EVENT_LOG_READ_FAILED (FileSystemError): Filesystem event log files exist but could not be read
          path: Path that failed to read
      - EVENT_LOG_PARSE_FAILED (ParseError): Event log file contents failed Zod schema validation
          path: Path of malformed file
          details: Zod error message
      - INVALID_FILTER (ValidationError): Filter parameters fail Zod validation
          field: The invalid field name
          message: Validation error message

    Side effects: none
    Idempotent: yes
    """
    ...

def getActivityEventById(
    event_id: str,             # regex(^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$)
) -> DataResult:
    """
    Retrieves a single activity event by its unique ID.

    Preconditions:
      - event_id is a valid UUID v4 string

    Postconditions:
      - On status='ok', data contains a single ActivityEvent with matching id
      - On status='empty', no event with that ID exists

    Errors:
      - INVALID_EVENT_ID (ValidationError): event_id is not a valid UUID v4
      - EVENT_LOG_READ_FAILED (FileSystemError): Filesystem event log files could not be read

    Side effects: none
    Idempotent: yes
    """
    ...

def aggregateCostData(
    params: CostQueryParams = None,
) -> DataResult:
    """
    Aggregates cost data from filesystem cost log files into the CostDashboardResponse structure. Produces per-project breakdowns, per-agent breakdowns, and time-bucketed series. Returns DataResult wrapping CostDashboardResponse. Gracefully returns 'empty' status when no cost files are found (AC8).

    Preconditions:
      - If params.period_start is provided, it must be a valid ISO 8601 timestamp
      - If params.period_end is provided, it must be >= params.period_start

    Postconditions:
      - On status='ok', data contains CostDashboardResponse with all sections populated
      - On status='ok', total_cost_microdollars equals sum of all by_project entries
      - On status='ok', time_series data points are ordered chronologically
      - On status='empty', no cost log files were found on the filesystem — UI should show 'no data available' placeholder (AC8)
      - Each CostBreakdownEntry.total_cost_microdollars is the sum of its constituent CostRecords
      - Monetary values are always integer microdollars, never floating-point

    Errors:
      - COST_LOG_READ_FAILED (FileSystemError): Cost log files exist but could not be read from filesystem
          path: Path that failed
      - COST_LOG_PARSE_FAILED (ParseError): Cost log file contents failed Zod schema validation
          path: Path of malformed file
          details: Zod error message
      - INVALID_QUERY_PARAMS (ValidationError): Query parameters fail Zod validation
          field: Invalid field
          message: Error message

    Side effects: none
    Idempotent: yes
    """
    ...

def listCostRecords(
    params: CostQueryParams = None,
    pagination: CursorPagination = None,
) -> DataResult:
    """
    Lists raw cost records from filesystem, filtered by project/agent/time. Lower-level than aggregateCostData — used for detailed drill-down views.

    Postconditions:
      - On status='ok', data contains list of CostRecord ordered by timestamp descending
      - On status='empty', no cost records match the filter criteria or no cost files found
      - All returned records match the provided filter criteria

    Errors:
      - COST_LOG_READ_FAILED (FileSystemError): Cost log files could not be read
      - COST_LOG_PARSE_FAILED (ParseError): Cost log contents malformed

    Side effects: none
    Idempotent: yes
    """
    ...

def aggregateTokenUsage(
    params: CostQueryParams,
) -> DataResult:
    """
    Aggregates token usage data into time-bucketed series for charting. Returns DataResult wrapping TokenUsageList.

    Preconditions:
      - params.granularity is a valid TimeBucketGranularity value

    Postconditions:
      - On status='ok', data contains TokenUsageList ordered chronologically
      - Each TokenUsage.total_tokens equals input_tokens + output_tokens
      - On status='empty', no token data found for the queried period

    Errors:
      - COST_LOG_READ_FAILED (FileSystemError): Cost log files could not be read
      - COST_LOG_PARSE_FAILED (ParseError): Cost log contents malformed

    Side effects: none
    Idempotent: yes
    """
    ...

def getBurnRate(
    window_hours: int,         # range(1..720)
) -> DataResult:
    """
    Calculates the current cost burn rate over a configurable time window. Used in the overview dashboard for the burn rate card.

    Preconditions:
      - window_hours is between 1 and 720

    Postconditions:
      - On status='ok', data contains BurnRate with rate calculated over the specified window
      - On status='ok', trend is calculated by comparing current window to the immediately preceding window of equal length
      - On status='empty', no cost data exists for the specified window

    Errors:
      - COST_LOG_READ_FAILED (FileSystemError): Cost log files could not be read
      - INSUFFICIENT_DATA (DataError): Some cost data exists but not enough for trend calculation

    Side effects: none
    Idempotent: yes
    """
    ...

def createBudgetAlert(
    input: BudgetAlertCreateInput,
) -> BudgetAlertCrudResponse:
    """
    Creates a new budget alert configuration in SQLite. Validates input via Zod schema. Returns the created alert.

    Preconditions:
      - input passes Zod schema validation
      - If scope_type is 'project' or 'agent', scope_id must be non-empty
      - If scope_type is 'global', scope_id must be empty

    Postconditions:
      - On success=true, alert is persisted in SQLite with a generated UUID v4 id
      - On success=true, alert.created_at and alert.updated_at are set to current ISO 8601 timestamp
      - On success=true, alert.last_triggered_at is empty string (never triggered)
      - On success=true, response.alert contains the complete persisted alert

    Errors:
      - VALIDATION_FAILED (ValidationError): Input fails Zod schema validation
          field: Invalid field
          message: Validation error
      - SCOPE_ID_REQUIRED (ValidationError): scope_type is 'project' or 'agent' but scope_id is empty
          field: scope_id
          message: scope_id required for non-global scope
      - SCOPE_ENTITY_NOT_FOUND (NotFoundError): scope_id references a project or agent that doesn't exist
          entity_type: project or agent
          entity_id: The invalid ID
      - DB_WRITE_FAILED (DatabaseError): SQLite insert failed
          details: SQLite error message

    Side effects: none
    Idempotent: no
    """
    ...

def updateBudgetAlert(
    alert_id: str,             # regex(^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$)
    input: BudgetAlertUpdateInput,
) -> BudgetAlertCrudResponse:
    """
    Updates an existing budget alert configuration in SQLite. Partial update — only provided fields are modified.

    Preconditions:
      - alert_id is a valid UUID v4
      - At least one field in input is provided (non-empty update)

    Postconditions:
      - On success=true, alert.updated_at is set to current ISO 8601 timestamp
      - On success=true, only the provided fields are modified; other fields remain unchanged
      - On success=true, response.alert contains the complete updated alert
      - If enabled is changed from false to true, last_triggered_at is reset to empty

    Errors:
      - ALERT_NOT_FOUND (NotFoundError): No alert exists with the given alert_id
          alert_id: The missing alert ID
      - VALIDATION_FAILED (ValidationError): Update input fails Zod schema validation
          field: Invalid field
          message: Validation error
      - EMPTY_UPDATE (ValidationError): No fields provided in the update input
          message: At least one field must be provided for update
      - DB_WRITE_FAILED (DatabaseError): SQLite update failed
          details: SQLite error message

    Side effects: none
    Idempotent: yes
    """
    ...

def deleteBudgetAlert(
    alert_id: str,             # regex(^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$)
) -> BudgetAlertCrudResponse:
    """
    Deletes a budget alert configuration from SQLite by ID.

    Preconditions:
      - alert_id is a valid UUID v4

    Postconditions:
      - On success=true, the alert is removed from SQLite
      - On success=true, response.deleted_id equals the input alert_id
      - Subsequent getBudgetAlert(alert_id) returns not found

    Errors:
      - ALERT_NOT_FOUND (NotFoundError): No alert exists with the given alert_id
          alert_id: The missing alert ID
      - DB_WRITE_FAILED (DatabaseError): SQLite delete failed
          details: SQLite error message

    Side effects: none
    Idempotent: yes
    """
    ...

def getBudgetAlert(
    alert_id: str,             # regex(^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$)
) -> BudgetAlertCrudResponse:
    """
    Retrieves a single budget alert configuration by ID from SQLite.

    Preconditions:
      - alert_id is a valid UUID v4

    Postconditions:
      - On success=true, response.alert contains the full BudgetAlert with matching ID
      - On success=false with ALERT_NOT_FOUND, no alert exists with that ID

    Errors:
      - ALERT_NOT_FOUND (NotFoundError): No alert exists with the given alert_id
          alert_id: The missing alert ID
      - DB_READ_FAILED (DatabaseError): SQLite query failed
          details: SQLite error message

    Side effects: none
    Idempotent: yes
    """
    ...

def listBudgetAlerts(
    scope_type: BudgetAlertScopeType = None,
    scope_id: str = None,
    enabled_only: bool = false,
) -> BudgetAlertCrudResponse:
    """
    Lists all budget alert configurations from SQLite. Optionally filtered by scope.

    Preconditions:
      - If scope_id is provided, scope_type must also be provided

    Postconditions:
      - On success=true, response.alerts contains all matching BudgetAlerts ordered by created_at descending
      - If no alerts match, response.alerts is an empty list (still success=true)

    Errors:
      - INVALID_FILTER (ValidationError): scope_id provided without scope_type
          message: scope_type required when scope_id is provided
      - DB_READ_FAILED (DatabaseError): SQLite query failed
          details: SQLite error message

    Side effects: none
    Idempotent: yes
    """
    ...

def evaluateBudgetAlerts() -> BudgetAlertList:
    """
    Evaluates all enabled budget alerts against current cost data. For each alert whose threshold is crossed, updates last_triggered_at and emits a 'cost.threshold_crossed' SSE event. Called periodically by the data layer (e.g., on new cost data detection).

    Preconditions:
      - SQLite database is accessible
      - Cost data files are accessible on filesystem

    Postconditions:
      - Returns list of BudgetAlerts that were triggered in this evaluation
      - Each triggered alert has last_triggered_at updated to current ISO 8601 timestamp in SQLite
      - A 'cost.threshold_crossed' SSE event is emitted for each newly triggered alert
      - Alerts that were already triggered within their debounce window are not re-triggered
      - Alerts with enabled=false are skipped

    Errors:
      - DB_READ_FAILED (DatabaseError): Failed to read alerts from SQLite
      - DB_WRITE_FAILED (DatabaseError): Failed to update last_triggered_at in SQLite
      - COST_DATA_UNAVAILABLE (FileSystemError): Cost data files could not be read for threshold evaluation
      - SSE_EMIT_FAILED (SSEError): Failed to emit SSE event for triggered alert

    Side effects: none
    Idempotent: no
    """
    ...

def getDashboardOverview() -> DashboardOverviewResponse:
    """
    Assembles the composite dashboard overview by aggregating data from multiple sources: agent status from OpenClaw filesystem, active project count, PACT health from PACT CLI, last 10 activity events, and cost burn rate. Each section is independently fetched and wrapped in DataResult so partial failures don't block the entire dashboard.

    Postconditions:
      - generated_at is set to current ISO 8601 timestamp
      - Each section (agent_summary, active_projects_count, pact_health, recent_activity, burn_rate) is independently a DataResult
      - If a section's data source is unavailable, that section returns DataResultEmpty or DataResultError while other sections still return normally
      - recent_activity contains at most 10 events on status='ok'
      - All monetary values in burn_rate are integer microdollars

    Errors:
      - TOTAL_FAILURE (ServiceUnavailableError): All data sources are simultaneously unavailable
          message: All dashboard data sources are unavailable

    Side effects: none
    Idempotent: yes
    """
    ...

def getAgentStatusSummary() -> DataResult:
    """
    Reads agent configuration and session data from OpenClaw filesystem and produces an AgentStatusSummary. Used by getDashboardOverview and potentially standalone.

    Postconditions:
      - On status='ok', data contains AgentStatusSummary where total = active + idle + errored + stopped
      - On status='empty', no agent configuration files found

    Errors:
      - AGENT_CONFIG_READ_FAILED (FileSystemError): Agent configuration directory could not be read
      - AGENT_SESSION_PARSE_FAILED (ParseError): Agent session files are malformed

    Side effects: none
    Idempotent: yes
    """
    ...

def getPactHealthSnapshot() -> DataResult:
    """
    Reads PACT state data from the filesystem and optionally calls the PACT CLI to produce a PactHealthSnapshot.

    Postconditions:
      - On status='ok', data contains PactHealthSnapshot with last_check_at set to current timestamp
      - On status='empty', PACT state directory does not exist or is empty
      - Approval/rejection/timeout counts cover the last 24 hours

    Errors:
      - PACT_STATE_READ_FAILED (FileSystemError): PACT state directory could not be read
      - PACT_CLI_FAILED (CLIError): PACT CLI invocation failed or timed out
          exit_code: CLI exit code
          stderr: CLI error output
      - PACT_STATE_PARSE_FAILED (ParseError): PACT state files are malformed

    Side effects: none
    Idempotent: yes
    """
    ...

def subscribeToEvents(
    filters: SSEFilterParams = None,
) -> SSEMessage:
    """
    Establishes a Server-Sent Events (SSE) connection at /api/events. Multiplexes all event types through a single endpoint. Supports filter query params and reconnection via lastEventId. The SSE stream sends heartbeat events every 30 seconds to keep the connection alive.

    Preconditions:
      - If last_event_id is provided, it should be a valid event ID for replay
      - Client supports SSE (EventSource API or compatible)

    Postconditions:
      - Returns a streaming SSE response with Content-Type: text/event-stream
      - Each SSE message includes id, event, and data fields
      - Heartbeat events are sent every 30 seconds with event='heartbeat'
      - If last_event_id is provided, missed events since that ID are replayed before live streaming
      - Only events matching the provided filters are sent to this client
      - Initial message includes retry field suggesting 3000ms reconnection delay

    Errors:
      - INVALID_FILTER_PARAMS (ValidationError): Filter query params fail Zod validation
      - EVENT_REPLAY_FAILED (ReplayError): Could not replay events from last_event_id (too old or invalid)
          last_event_id: The requested event ID
          reason: Why replay failed
      - STREAM_ERROR (SSEError): SSE event bus encounters an internal error

    Side effects: none
    Idempotent: yes
    """
    ...

def transformCostRecordsToChartData(
    records: CostRecordList,
    group_by: str,             # custom(group_by === 'project' || group_by === 'agent' || group_by === 'time')
    granularity: TimeBucketGranularity = day,
) -> CostChartDataPointList:
    """
    Pure transformation function in lib/data/transforms.ts. Converts a list of CostRecords into CostChartDataPointList shaped for recharts consumption. Groups by the specified dimension (project, agent, or time bucket).

    Preconditions:
      - records is a valid CostRecordList (may be empty)
      - group_by is one of 'project', 'agent', 'time'

    Postconditions:
      - Output length equals number of unique groups in the input
      - Each data point's cost_dollars equals cost_microdollars / 1_000_000
      - If records is empty, returns empty list
      - When group_by='time', data points are ordered chronologically
      - When group_by='project' or 'agent', data points are ordered by cost descending

    Side effects: none
    Idempotent: yes
    """
    ...

def transformTokenUsageToChartData(
    usage_data: TokenUsageList,
) -> TokenChartDataPointList:
    """
    Pure transformation function in lib/data/transforms.ts. Converts TokenUsageList into TokenChartDataPointList shaped for recharts line chart consumption.

    Preconditions:
      - usage_data is a valid TokenUsageList (may be empty)

    Postconditions:
      - Output has same length as input
      - Each data point's total_tokens equals input_tokens + output_tokens
      - Data points are in the same chronological order as the input
      - If usage_data is empty, returns empty list
      - Labels are human-readable time strings derived from period_start

    Side effects: none
    Idempotent: yes
    """
    ...

def getActiveProjectsCount() -> DataResult:
    """
    Reads OpenClaw project configuration from the filesystem and returns the count of active (non-archived) projects.

    Postconditions:
      - On status='ok', data contains an integer >= 0 representing active project count
      - On status='empty', no project configuration files found
      - Archived projects are excluded from the count

    Errors:
      - PROJECT_CONFIG_READ_FAILED (FileSystemError): Project configuration directory could not be read
      - PROJECT_CONFIG_PARSE_FAILED (ParseError): Project configuration files are malformed

    Side effects: none
    Idempotent: yes
    """
    ...

# ── REQUIRED EXPORTS ──────────────────────────────────
# Your implementation module MUST export ALL of these names
# with EXACTLY these spellings. Tests import them by name.
# __all__ = ['ActivityEventType', 'DataResultStatus', 'DataResultOk', 'DataResultEmpty', 'DataResultError', 'DataResult', 'ActivityEvent', 'EventSeverity', 'ActivityFilter', 'StringList', 'ActivityEventTypeList', 'EventSeverityList', 'CursorPagination', 'ActivityEventList', 'ActivityFeedResponse', 'CostRecord', 'TokenUsage', 'BudgetAlert', 'BudgetAlertScopeType', 'BudgetAlertPeriod', 'BudgetAlertCreateInput', 'BudgetAlertUpdateInput', 'BudgetAlertList', 'BudgetAlertCrudResponse', 'CostBreakdownEntry', 'CostBreakdownList', 'TimeBucketGranularity', 'CostChartDataPoint', 'CostChartDataPointList', 'TokenChartDataPoint', 'TokenChartDataPointList', 'TokenUsageList', 'CostTimeSeries', 'CostDashboardResponse', 'BurnRate', 'BurnRateTrend', 'AgentStatusSummary', 'PactHealthSnapshot', 'DashboardOverviewResponse', 'SSEFilterParams', 'SSEMessage', 'CostRecordList', 'CostQueryParams', 'listActivityEvents', 'ValidationError', 'FileSystemError', 'ParseError', 'getActivityEventById', 'aggregateCostData', 'listCostRecords', 'aggregateTokenUsage', 'getBurnRate', 'DataError', 'createBudgetAlert', 'NotFoundError', 'DatabaseError', 'updateBudgetAlert', 'deleteBudgetAlert', 'getBudgetAlert', 'listBudgetAlerts', 'evaluateBudgetAlerts', 'SSEError', 'getDashboardOverview', 'ServiceUnavailableError', 'getAgentStatusSummary', 'getPactHealthSnapshot', 'CLIError', 'subscribeToEvents', 'ReplayError', 'transformCostRecordsToChartData', 'transformTokenUsageToChartData', 'getActiveProjectsCount']
