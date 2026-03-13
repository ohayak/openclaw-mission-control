"""
Agent Dashboard Component

Provides agent overview and detail pages with session history, token usage tracking,
task management, and real-time SSE updates for the Mission Control dashboard.
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Dict, List, Union, Literal
from dataclasses import dataclass, field


# ============================================================================
# ENUMS & CONSTANTS (as simple classes with string attributes)
# ============================================================================

class AgentStatusKind:
    """Discriminant for the AgentStatus union."""
    active = "active"
    idle = "idle"
    error = "error"


class SessionExitStatus:
    """How an agent session terminated."""
    running = "running"
    completed = "completed"
    error = "error"
    timeout = "timeout"
    cancelled = "cancelled"


class TaskStatus:
    """Task lifecycle status."""
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TaskPriority:
    """Task priority levels."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TimeRange:
    """Predefined time range for filtering token usage data."""
    h1 = "1h"
    h6 = "6h"
    h24 = "24h"
    d7 = "7d"
    d30 = "30d"
    all = "all"


class DataErrorKind:
    """Discriminant for DataError union."""
    file_not_found = "file_not_found"
    file_parse_error = "file_parse_error"
    db_error = "db_error"
    agent_not_found = "agent_not_found"
    validation_error = "validation_error"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class AgentStatusActive:
    """Status payload when agent is actively running a session."""
    kind: Literal["active"]
    current_session_id: str
    started_at: str
    current_task_description: Optional[str] = None


@dataclass
class AgentStatusIdle:
    """Status payload when agent is idle (not running)."""
    kind: Literal["idle"]
    last_active_at: Optional[str] = None


@dataclass
class AgentStatusError:
    """Status payload when agent is in an error state."""
    kind: Literal["error"]
    error_message: str
    occurred_at: str
    error_code: Optional[str] = None


# Type alias for AgentStatus union
AgentStatus = Union[AgentStatusActive, AgentStatusIdle, AgentStatusError]


@dataclass
class TokenUsageSummary:
    """Cumulative token usage counters for an agent."""
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    session_count: int


@dataclass
class Agent:
    """Summary representation of an agent for the list page."""
    id: str  # AgentId branded type (runtime: string)
    name: str
    model: str
    status: Union[AgentStatusActive, AgentStatusIdle, AgentStatusError]  # AgentStatus union
    token_usage: Union[TokenUsageSummary, Dict[str, Any]]  # TokenUsageSummary instance or dict
    assigned_task_count: int
    tags: List[str] = field(default_factory=list)


@dataclass
class AgentSession:
    """A single agent work session with timing and token data."""
    session_id: str
    agent_id: str
    started_at: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    ended_at: Optional[str] = None
    duration_seconds: int = 0
    exit_status: str = "running"
    task_description: Optional[str] = None


@dataclass
class AgentTask:
    """A task assigned to an agent, stored in SQLite."""
    task_id: str
    agent_id: str
    title: str
    status: str
    priority: str
    created_at: str
    updated_at: str
    description: Optional[str] = None
    completed_at: Optional[str] = None
    project_id: Optional[str] = None


@dataclass
class TokenUsageDataPoint:
    """A single data point for the recharts token usage line chart."""
    timestamp: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    session_count: int


@dataclass
class AgentDetail:
    """Full agent detail for the detail page."""
    agent: Dict[str, Any]  # Agent as dict
    recent_sessions: List[Dict[str, Any]]
    assigned_tasks: List[Dict[str, Any]]
    token_usage_timeline: List[Dict[str, Any]]
    total_sessions: int


@dataclass
class PaginationParams:
    """Pagination parameters for list queries."""
    page: int
    page_size: int


@dataclass
class PaginatedResult:
    """Generic paginated result wrapper."""
    items: List[Any]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


@dataclass
class DataError:
    """Structured error type returned from data access layer."""
    kind: str  # DataErrorKind
    message: str
    source_path: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRawConfig:
    """Raw agent entry as parsed from openclaw.json."""
    id: str
    name: str
    model: str
    status: str
    current_session: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    error: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OpenClawConfig:
    """Top-level openclaw.json structure."""
    agents: List[Dict[str, Any]]
    version: str = "1.0"
    base_path: Optional[str] = None
    sessions_dir: str = "sessions"


@dataclass
class AgentActivityEvent:
    """A single activity event for the agent activity feed."""
    event_id: str
    agent_id: str
    event_type: str
    timestamp: str
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# RESULT TYPE
# ============================================================================

def make_result_ok(data: Any) -> Dict[str, Any]:
    """Create a successful Result."""
    return {"ok": True, "data": data}


def make_result_err(kind: str, message: str, source_path: str = "", details: Optional[Dict] = None) -> Dict[str, Any]:
    """Create an error Result."""
    return {
        "ok": False,
        "error": {
            "kind": kind,
            "message": message,
            "source_path": source_path,
            "details": details or {},
        },
    }


# ============================================================================
# VALIDATION & UTILITIES
# ============================================================================

ISO_8601_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
AGENT_ID_REGEX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def is_valid_agent_id(agent_id: str) -> bool:
    """Validate AgentId format."""
    return bool(agent_id) and bool(AGENT_ID_REGEX.match(agent_id))


def is_iso8601(timestamp: str) -> bool:
    """Check if string is ISO 8601 format."""
    return bool(ISO_8601_REGEX.match(timestamp))


def iso_now() -> str:
    """Get current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# DATA ACCESS LAYER
# ============================================================================

def parseOpenClawConfig(config_path: str) -> Dict[str, Any]:
    """
    Parse and validate openclaw.json from the filesystem.
    Returns Result<OpenClawConfig, DataError>.
    """
    try:
        # Check if file exists
        if not os.path.exists(config_path):
            return make_result_err(
                "file_not_found",
                f"Config file not found: {config_path}",
                source_path=config_path
            )

        # Try to read file
        try:
            with open(config_path, 'r') as f:
                content = f.read()
        except PermissionError:
            return make_result_err(
                "file_parse_error",
                "Permission denied",
                source_path=config_path
            )
        except Exception as e:
            return make_result_err(
                "file_parse_error",
                f"Cannot read file: {str(e)}",
                source_path=config_path
            )

        # Try to parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return make_result_err(
                "file_parse_error",
                f"Invalid JSON: {str(e)}",
                source_path=config_path
            )

        # Validate required fields
        if not isinstance(data, dict):
            return make_result_err(
                "validation_error",
                "Config must be a JSON object",
                source_path=config_path
            )

        if "agents" not in data:
            return make_result_err(
                "validation_error",
                "Missing required field: agents",
                source_path=config_path,
                details={"missing_field": "agents"}
            )

        if not isinstance(data["agents"], list):
            return make_result_err(
                "validation_error",
                "Field 'agents' must be an array",
                source_path=config_path
            )

        # Validate each agent
        for i, agent in enumerate(data["agents"]):
            if not isinstance(agent, dict):
                return make_result_err(
                    "validation_error",
                    f"Agent at index {i} is not an object",
                    source_path=config_path
                )

            required_fields = ["id", "name", "model", "status"]
            for field_name in required_fields:
                if field_name not in agent:
                    return make_result_err(
                        "validation_error",
                        f"Agent at index {i} missing required field: {field_name}",
                        source_path=config_path,
                        details={"agent_index": i, "missing_field": field_name}
                    )

        # Return validated config
        config = {
            "version": data.get("version", "1.0"),
            "agents": data["agents"],
            "base_path": data.get("base_path"),
            "sessions_dir": data.get("sessions_dir", "sessions"),
        }

        return make_result_ok(config)

    except Exception as e:
        return make_result_err(
            "file_parse_error",
            f"Unexpected error: {str(e)}",
            source_path=config_path
        )


def mapRawAgentToDomain(
    raw: Dict[str, Any],
    token_usage: Dict[str, Any],
    assigned_task_count: int
) -> Union[Agent, Dict[str, Any]]:
    """
    Transform a raw AgentRawConfig into the domain Agent type.
    Maps raw status strings to the AgentStatus discriminated union.
    Returns an Agent dataclass instance or an error Result dict.
    """
    # Validate agent ID
    agent_id = raw.get("id", "")
    if not is_valid_agent_id(agent_id):
        return make_result_err(
            "validation_error",
            f"Invalid agent ID format: {agent_id}"
        )

    # Map status to AgentStatus union
    status_str = raw.get("status", "idle")

    if status_str == "active":
        current_session = raw.get("current_session", {})
        status = AgentStatusActive(
            kind="active",
            current_session_id=current_session.get("session_id", ""),
            started_at=current_session.get("started_at", iso_now()),
            current_task_description=current_session.get("task_description"),
        )
    elif status_str == "idle":
        status = AgentStatusIdle(
            kind="idle",
            last_active_at=raw.get("last_active_at", iso_now()),
        )
    elif status_str == "error":
        error_info = raw.get("error", {})
        status = AgentStatusError(
            kind="error",
            error_message=error_info.get("message", "Unknown error"),
            occurred_at=error_info.get("occurred_at", iso_now()),
            error_code=error_info.get("code"),
        )
    else:
        # Raise exception for unknown status (case-sensitive)
        raise ValueError(f"unknown_status: '{status_str}'")

    # Convert token_usage to dataclass if it's a dict
    if isinstance(token_usage, dict):
        token_usage_obj = TokenUsageSummary(
            total_input_tokens=token_usage.get("total_input_tokens", 0),
            total_output_tokens=token_usage.get("total_output_tokens", 0),
            total_tokens=token_usage.get("total_tokens", 0),
            estimated_cost_usd=token_usage.get("estimated_cost_usd", 0.0),
            session_count=token_usage.get("session_count", 0),
        )
    else:
        token_usage_obj = token_usage

    # Build Agent dataclass instance
    agent = Agent(
        id=agent_id,
        name=raw.get("name", ""),
        model=raw.get("model", ""),
        status=status,  # Now an actual dataclass instance
        token_usage=token_usage_obj,  # Now an actual dataclass instance
        assigned_task_count=assigned_task_count,
        tags=raw.get("tags", []),
    )

    return agent


def getAgents() -> Dict[str, Any]:
    """
    Fetch all agents from openclaw.json, join with SQLite for task counts and token usage.
    Returns Result<List[Agent], DataError>.
    """
    # This is a stub implementation that would be mocked in tests
    # In real implementation, this would:
    # 1. Call parseOpenClawConfig
    # 2. Query SQLite for task counts
    # 3. Aggregate token usage from session data
    # 4. Map each raw agent to domain Agent
    # 5. Sort by name alphabetically

    return make_result_ok([])


def getAgentById(agent_id: str) -> Dict[str, Any]:
    """
    Fetch a single agent by ID.
    Returns Result<Agent, DataError>.
    """
    if not is_valid_agent_id(agent_id):
        return make_result_err(
            "validation_error",
            f"Invalid agent ID: {agent_id}"
        )

    # Stub implementation - would be mocked in tests
    return make_result_err(
        "agent_not_found",
        f"Agent not found: {agent_id}"
    )


def getAgentSessions(
    agent_id: str,
    pagination: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Fetch paginated session history for a specific agent.
    Returns Result<PaginatedResult<AgentSession>, DataError>.
    """
    if not is_valid_agent_id(agent_id):
        return make_result_err(
            "validation_error",
            f"Invalid agent ID: {agent_id}"
        )

    page = pagination.get("page", 1)
    page_size = pagination.get("page_size", 20)

    # Stub implementation
    return make_result_ok({
        "items": [],
        "total_count": 0,
        "page": page,
        "page_size": page_size,
        "has_next": False,
        "has_previous": page > 1,
    })


def getAgentTokenUsage(
    agent_id: str,
    time_range: str
) -> Dict[str, Any]:
    """
    Fetch time-bucketed token usage data for an agent over a time range.
    Returns Result<List[TokenUsageDataPoint], DataError>.
    """
    if not is_valid_agent_id(agent_id):
        return make_result_err(
            "validation_error",
            f"Invalid agent ID: {agent_id}"
        )

    # Validate time_range
    valid_ranges = ["1h", "6h", "24h", "7d", "30d", "all"]
    if time_range not in valid_ranges:
        return make_result_err(
            "validation_error",
            f"Invalid time range: {time_range}"
        )

    # Stub implementation
    return make_result_ok([])


def getAgentTasks(agent_id: str) -> Dict[str, Any]:
    """
    Fetch all tasks assigned to a specific agent from SQLite.
    Returns Result<List[AgentTask], DataError>.
    """
    if not is_valid_agent_id(agent_id):
        return make_result_err(
            "validation_error",
            f"Invalid agent ID: {agent_id}"
        )

    # Stub implementation
    return make_result_ok([])


def getAgentDetail(
    agent_id: str,
    session_pagination: Optional[Dict[str, Any]] = None,
    token_time_range: str = "7d"
) -> Dict[str, Any]:
    """
    Compose full agent detail by calling sub-functions.
    Returns Result<AgentDetail, DataError>.
    """
    if not is_valid_agent_id(agent_id):
        return make_result_err(
            "validation_error",
            f"Invalid agent ID: {agent_id}"
        )

    # Stub implementation
    return make_result_err(
        "agent_not_found",
        f"Agent not found: {agent_id}"
    )


def getAgentActivityEvents(
    agent_id: str,
    limit: int
) -> Dict[str, Any]:
    """
    Fetch recent activity events for an agent.
    Returns Result<List[AgentActivityEvent], DataError>.
    """
    if not is_valid_agent_id(agent_id):
        return make_result_err(
            "validation_error",
            f"Invalid agent ID: {agent_id}"
        )

    if limit < 1 or limit > 500:
        return make_result_err(
            "validation_error",
            f"Invalid limit: {limit} (must be 1-500)"
        )

    # Stub implementation
    return make_result_ok([])


# ============================================================================
# API ROUTE HANDLERS
# ============================================================================

def handleGetAgents() -> Dict[str, Any]:
    """
    API route handler for GET /api/agents.
    Returns AgentListResponse or AgentErrorResponse.
    """
    # Stub implementation - would be mocked in tests
    return {
        "agents": [],
        "total_count": 0,
        "fetched_at": iso_now(),
    }


def handleGetAgentById(
    agent_id: str,
    time_range: str = "7d",
    sessions_page: int = 1,
    sessions_page_size: int = 20
) -> Dict[str, Any]:
    """
    API route handler for GET /api/agents/[agentId].
    Returns AgentDetailResponse or AgentErrorResponse.
    """
    # Validate agent_id
    if not is_valid_agent_id(agent_id):
        return {
            "error": "invalid_agent_id",
            "message": f"Invalid agent ID format: {agent_id}",
            "details": {},
            "status_code": 400,
        }

    # Validate pagination params
    if sessions_page < 1:
        return {
            "error": "invalid_query_params",
            "message": "Page must be >= 1",
            "details": {},
            "status_code": 400,
        }

    if sessions_page_size < 1 or sessions_page_size > 100:
        return {
            "error": "invalid_query_params",
            "message": "Page size must be 1-100",
            "details": {},
            "status_code": 400,
        }

    # Validate time_range
    valid_ranges = ["1h", "6h", "24h", "7d", "30d", "all"]
    if time_range not in valid_ranges:
        return {
            "error": "invalid_query_params",
            "message": f"Invalid time range: {time_range}",
            "details": {},
            "status_code": 400,
        }

    # Stub implementation
    return {
        "error": "agent_not_found",
        "message": f"Agent not found: {agent_id}",
        "details": {},
        "status_code": 404,
    }


# ============================================================================
# SSE EVENT SYSTEM
# ============================================================================

def emitAgentSSEEvent(event: Dict[str, Any]) -> None:
    """
    Emit an agent-related SSE event to the event bus.
    Called by file watchers when openclaw.json or session files change.
    """
    # Validate event type has 'agent:' prefix
    event_type = event.get("type", "")
    if not event_type.startswith("agent:"):
        raise ValueError(f"Agent SSE events must have 'agent:' prefix, got: {event_type}")

    # In real implementation, this would:
    # 1. Validate event structure
    # 2. Enqueue on SSE event bus
    # 3. Handle filtering by agent_id
    # 4. Serialize to JSON for SSE data field

    # Stub implementation
    pass


# ============================================================================
# COMPONENT PROPS (for documentation/type checking)
# ============================================================================

# These are TypeScript/React component prop types, included for completeness
# In Python implementation, these serve as documentation

AgentCardProps = Dict[str, Any]
AgentStatusBadgeProps = Dict[str, Any]
TokenUsageChartProps = Dict[str, Any]
AgentActivityFeedProps = Dict[str, Any]
AgentSessionListProps = Dict[str, Any]
AgentTaskListProps = Dict[str, Any]
AgentListErrorStateProps = Dict[str, Any]

# SSE Event types
SSEAgentStatusChanged = Dict[str, Any]
SSEAgentSessionStarted = Dict[str, Any]
SSEAgentSessionEnded = Dict[str, Any]
SSEAgentEvent = Union[
    Dict[str, Any],  # SSEAgentStatusChanged
    Dict[str, Any],  # SSEAgentSessionStarted
    Dict[str, Any],  # SSEAgentSessionEnded
]

# API Response types
AgentListResponse = Dict[str, Any]
AgentDetailResponse = Dict[str, Any]
AgentErrorResponse = Dict[str, Any]
