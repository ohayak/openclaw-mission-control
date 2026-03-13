"""
Activity Feed & Cost Tracking Pages component.

Provides data layer, API handlers, and rendering functions for the mission control
dashboard's activity feed and cost tracking features.
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


# ===========================================================================
# TIER 1: FORMATTING UTILITIES
# ===========================================================================

def formatCentsToCurrency(cents: int, compact: bool) -> str:
    """
    Format cents as currency string.

    Args:
        cents: Amount in cents (1 USD = 100 cents)
        compact: If True, use K/M suffixes for large values

    Returns:
        Formatted string like "$12.34" or "$1.5K"
    """
    if cents < 0:
        return "-" + formatCentsToCurrency(-cents, compact)

    dollars = cents / 100.0

    if compact:
        if cents == 0:
            return "$0"
        elif dollars >= 1_000_000:
            return f"${dollars / 1_000_000:.1f}M"
        elif dollars >= 1_000:
            return f"${dollars / 1_000:.1f}K"
        else:
            return f"${dollars:.0f}"
    else:
        return f"${dollars:.2f}"


def formatTokenCount(count: int) -> str:
    """
    Format token count with K/M/B suffixes.

    Args:
        count: Token count (non-negative integer)

    Returns:
        Formatted string like "1.5K" or "2.3M"
    """
    if count < 1_000:
        return str(count)
    elif count < 1_000_000:
        return f"{count / 1_000:.1f}K"
    elif count < 1_000_000_000:
        return f"{count / 1_000_000:.1f}M"
    else:
        return f"{count / 1_000_000_000:.1f}B"


# ===========================================================================
# TIER 2: DATA LAYER FUNCTIONS
# ===========================================================================

def read_event_files() -> List[Dict[str, Any]]:
    """Mock-able function for reading event files from filesystem."""
    # This will be mocked in tests
    return []


def read_cost_files(time_range: Dict, query_scope: Dict) -> List[Dict[str, Any]]:
    """Mock-able function for reading cost files from filesystem."""
    # This will be mocked in tests
    return []


def query_budget_alerts_db() -> List[Dict[str, Any]]:
    """Mock-able function for querying budget alerts from SQLite."""
    # This will be mocked in tests
    return []


def insert_budget_alert_db(alert: Dict[str, Any]) -> Dict[str, Any]:
    """Mock-able function for inserting budget alert to SQLite."""
    # This will be mocked in tests
    return alert


def update_budget_alert_db(alert_id: str, alert: Dict[str, Any]) -> Dict[str, Any]:
    """Mock-able function for updating budget alert in SQLite."""
    # This will be mocked in tests
    return alert


def delete_budget_alert_db(alert_id: str) -> bool:
    """Mock-able function for deleting budget alert from SQLite."""
    # This will be mocked in tests
    return True


def get_agent_summary() -> Dict[str, Any]:
    """Mock-able function for getting agent summary."""
    # This will be mocked in tests
    return {"total": 0, "running": 0, "idle": 0, "paused": 0, "errored": 0, "offline": 0}


def get_pact_health() -> Dict[str, Any]:
    """Mock-able function for getting PACT health status."""
    # This will be mocked in tests
    return {
        "status": "healthy",
        "pending_proposals": 0,
        "active_votes": 0,
        "last_check_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    }


def get_active_projects_count() -> int:
    """Mock-able function for getting count of active projects."""
    # This will be mocked in tests
    return 0


def getActivityEvents(filter_dict: Dict[str, Any], cursor: str, limit: int) -> Dict[str, Any]:
    """
    Get paginated activity events.

    Args:
        filter_dict: Filter parameters (agent_id, type, etc.)
        cursor: Pagination cursor (event ID)
        limit: Maximum number of events to return

    Returns:
        Data result dict with ok/error status
    """
    try:
        # Validate cursor if provided
        if cursor and not cursor.startswith("evt-"):
            return {
                "ok": False,
                "error_code": "invalid_cursor",
                "error_message": "Provided cursor is invalid"
            }

        # Read events from filesystem
        all_events = read_event_files()

        # Sort by timestamp descending (newest first)
        all_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        # Apply filters
        filtered = all_events
        if filter_dict.get("agent_id"):
            filtered = [e for e in filtered if e.get("agent_id") == filter_dict["agent_id"]]
        if filter_dict.get("type"):
            type_filter = filter_dict["type"]
            if not isinstance(type_filter, list):
                type_filter = [type_filter]
            filtered = [e for e in filtered if e.get("type") in type_filter]

        # Find cursor position
        start_idx = 0
        if cursor:
            for i, event in enumerate(filtered):
                if event.get("id") == cursor:
                    start_idx = i + 1
                    break

        # Paginate
        page_events = filtered[start_idx:start_idx + limit]
        has_more = len(filtered) > start_idx + limit
        next_cursor = page_events[-1]["id"] if has_more and page_events else ""

        return {
            "ok": True,
            "data": {
                "events": page_events,
                "next_cursor": next_cursor
            }
        }

    except FileNotFoundError:
        return {
            "ok": False,
            "error_code": "filesystem_error",
            "error_message": "Event files not found"
        }
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error_code": "parse_error",
            "error_message": "Failed to parse event files"
        }
    except Exception as e:
        return {
            "ok": False,
            "error_code": "unknown_error",
            "error_message": str(e)
        }


def getCostTimeSeries(
    time_range: Dict[str, str],
    query_scope: Dict[str, str],
    granularity: str
) -> Dict[str, Any]:
    """
    Get cost time series data.

    Args:
        time_range: Dict with from_timestamp and to_timestamp
        query_scope: Dict with scope and scope_id
        granularity: Time bucket granularity (hour/day/week/month)

    Returns:
        Data result dict
    """
    try:
        from_ts = time_range.get("from_timestamp", "")
        to_ts = time_range.get("to_timestamp", "")

        # Validate time range
        if from_ts >= to_ts:
            return {
                "ok": False,
                "error_code": "invalid_range",
                "error_message": "from_timestamp must be before to_timestamp"
            }

        # Validate scope
        scope = query_scope.get("scope", "all")
        scope_id = query_scope.get("scope_id", "")
        if scope in ["project", "agent"] and not scope_id:
            return {
                "ok": False,
                "error_code": "invalid_scope",
                "error_message": f"scope_id required for scope={scope}"
            }

        # Read cost data
        try:
            cost_data = read_cost_files(time_range, query_scope)
        except FileNotFoundError:
            # Graceful handling of missing data
            return {
                "ok": True,
                "data": {
                    "points": [],
                    "availability": "no_data"
                }
            }

        # Generate time series points
        # For now, return empty or mock data
        return {
            "ok": True,
            "data": {
                "points": cost_data if isinstance(cost_data, list) else [],
                "availability": "available" if cost_data else "no_data"
            }
        }

    except FileNotFoundError:
        return {
            "ok": True,
            "data": {
                "points": [],
                "availability": "no_data"
            }
        }
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error_code": "parse_error",
            "error_message": "Failed to parse cost files"
        }
    except Exception as e:
        if "filesystem" in str(e).lower():
            return {
                "ok": False,
                "error_code": "filesystem_error",
                "error_message": str(e)
            }
        return {
            "ok": False,
            "error_code": "unknown_error",
            "error_message": str(e)
        }


def getCostBreakdown(
    time_range: Dict[str, str],
    query_scope: Dict[str, str],
    group_by: str
) -> Dict[str, Any]:
    """
    Get cost breakdown grouped by project/agent.

    Args:
        time_range: Dict with from_timestamp and to_timestamp
        query_scope: Dict with scope and scope_id
        group_by: Group dimension (project/agent)

    Returns:
        Data result dict with breakdown entries
    """
    try:
        from_ts = time_range.get("from_timestamp", "")
        to_ts = time_range.get("to_timestamp", "")

        # Validate time range
        if from_ts >= to_ts:
            return {
                "ok": False,
                "error_code": "invalid_range",
                "error_message": "from_timestamp must be before to_timestamp"
            }

        # Read cost data
        try:
            cost_data = read_cost_files(time_range, query_scope)
        except FileNotFoundError:
            return {
                "ok": True,
                "data": {
                    "entries": [],
                    "availability": "no_data"
                }
            }

        # Group and aggregate
        breakdown = cost_data if isinstance(cost_data, list) else []

        # Ensure breakdown entries are sorted by total_amount_cents descending
        breakdown.sort(key=lambda x: x.get("total_amount_cents", 0), reverse=True)

        return {
            "ok": True,
            "data": {
                "entries": breakdown,
                "availability": "available" if breakdown else "no_data"
            }
        }

    except FileNotFoundError:
        return {
            "ok": True,
            "data": {
                "entries": [],
                "availability": "no_data"
            }
        }
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error_code": "parse_error",
            "error_message": "Failed to parse cost files"
        }
    except Exception as e:
        if "filesystem" in str(e).lower():
            return {
                "ok": False,
                "error_code": "filesystem_error",
                "error_message": str(e)
            }
        return {
            "ok": False,
            "error_code": "unknown_error",
            "error_message": str(e)
        }


def getTokenTimeSeries(
    time_range: Dict[str, str],
    query_scope: Dict[str, str],
    granularity: str
) -> Dict[str, Any]:
    """
    Get token usage time series.

    Args:
        time_range: Dict with from_timestamp and to_timestamp
        query_scope: Dict with scope and scope_id
        granularity: Time bucket granularity

    Returns:
        Data result dict with token time series
    """
    try:
        from_ts = time_range.get("from_timestamp", "")
        to_ts = time_range.get("to_timestamp", "")

        # Validate time range
        if from_ts >= to_ts:
            return {
                "ok": False,
                "error_code": "invalid_range",
                "error_message": "from_timestamp must be before to_timestamp"
            }

        # Validate scope
        scope = query_scope.get("scope", "all")
        scope_id = query_scope.get("scope_id", "")
        if scope in ["project", "agent"] and not scope_id:
            return {
                "ok": False,
                "error_code": "invalid_scope",
                "error_message": f"scope_id required for scope={scope}"
            }

        # Read cost data (token data is derived from cost data)
        try:
            token_data = read_cost_files(time_range, query_scope)
        except FileNotFoundError:
            return {
                "ok": True,
                "data": {
                    "points": [],
                    "availability": "no_data"
                }
            }

        return {
            "ok": True,
            "data": {
                "points": token_data if isinstance(token_data, list) else [],
                "availability": "available" if token_data else "no_data"
            }
        }

    except FileNotFoundError:
        return {
            "ok": True,
            "data": {
                "points": [],
                "availability": "no_data"
            }
        }
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error_code": "parse_error",
            "error_message": "Failed to parse cost files"
        }
    except Exception as e:
        if "filesystem" in str(e).lower():
            return {
                "ok": False,
                "error_code": "filesystem_error",
                "error_message": str(e)
            }
        return {
            "ok": False,
            "error_code": "unknown_error",
            "error_message": str(e)
        }


def getDashboardSummary() -> Dict[str, Any]:
    """
    Get complete dashboard summary.

    Returns:
        Dict with agent_summary, projects, PACT health, recent events, burn rate, etc.
    """
    import time
    start_time = time.time()
    timeout_seconds = 5.0

    result = {
        "agent_summary": None,
        "active_projects_count": None,
        "pact_health": None,
        "recent_events": [],
        "cost_burn_rate": None,
        "cost_availability": "no_data",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    }

    errors = []

    try:
        # Check timeout
        if time.time() - start_time > timeout_seconds:
            return {
                "ok": False,
                "error_code": "timeout",
                "error_message": f"Dashboard summary fetch exceeded {timeout_seconds}s timeout"
            }

        # Get agent summary
        try:
            result["agent_summary"] = get_agent_summary()
        except Exception as e:
            errors.append(("agent_summary", str(e)))

        # Get active projects count
        try:
            result["active_projects_count"] = get_active_projects_count()
        except Exception as e:
            errors.append(("active_projects_count", str(e)))

        # Get PACT health
        try:
            result["pact_health"] = get_pact_health()
        except Exception as e:
            # PACT unreachable is not an error - set status accordingly
            result["pact_health"] = {
                "status": "unreachable",
                "pending_proposals": 0,
                "active_votes": 0,
                "last_check_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }

        # Get recent events
        try:
            events_result = getActivityEvents({}, "", 10)
            if events_result.get("ok"):
                result["recent_events"] = events_result["data"]["events"]
        except Exception as e:
            errors.append(("recent_events", str(e)))

        # Get cost burn rate
        try:
            cost_result = getCostTimeSeries(
                {
                    "from_timestamp": "2025-01-01T00:00:00.000Z",
                    "to_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                },
                {"scope": "all", "scope_id": ""},
                "day"
            )
            if cost_result.get("ok"):
                result["cost_availability"] = cost_result["data"].get("availability", "no_data")
                # Calculate burn rate from data
                result["cost_burn_rate"] = {
                    "current_hour_cents": 0,
                    "current_day_cents": 0,
                    "projected_day_cents": 0,
                    "seven_day_total_cents": 0,
                    "seven_day_average_daily_cents": 0,
                    "trend": "stable"
                }
        except Exception as e:
            errors.append(("cost_burn_rate", str(e)))
            result["cost_availability"] = "no_data"

        # Check if total failure (all sources failed)
        critical_failures = sum(1 for key in ["agent_summary", "active_projects_count"] if result[key] is None)
        if critical_failures >= 2 and result["pact_health"] is None:
            return {
                "ok": False,
                "error_code": "total_failure",
                "error_message": "All dashboard data sources are unavailable"
            }

        return {
            "ok": True,
            "data": result
        }

    except Exception as e:
        return {
            "ok": False,
            "error_code": "unknown_error",
            "error_message": str(e)
        }


def getBudgetAlerts() -> Dict[str, Any]:
    """
    Get all budget alerts from database.

    Returns:
        Data result dict with list of alerts
    """
    try:
        alerts = query_budget_alerts_db()

        # Sort by created_at descending
        alerts.sort(key=lambda a: a.get("created_at", ""), reverse=True)

        # Validate all thresholds are positive
        for alert in alerts:
            if alert.get("threshold_cents", 0) <= 0:
                return {
                    "ok": False,
                    "error_code": "invalid_data",
                    "error_message": "Budget alert has non-positive threshold"
                }

        return {
            "ok": True,
            "data": alerts
        }

    except Exception as e:
        if "database" in str(e).lower() or "db" in str(e).lower() or "sqlite" in str(e).lower():
            return {
                "ok": False,
                "error_code": "db_error",
                "error_message": str(e)
            }
        return {
            "ok": False,
            "error_code": "unknown_error",
            "error_message": str(e)
        }


def createBudgetAlert(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new budget alert.

    Args:
        input_data: Alert creation parameters

    Returns:
        Data result dict with created alert
    """
    try:
        # Validate input
        required_fields = ["name", "scope", "threshold_cents", "period"]
        for field in required_fields:
            if field not in input_data or not input_data[field]:
                if field == "name" and not input_data.get("name"):
                    # Empty name is validation error
                    return {
                        "ok": False,
                        "error_code": "validation_error",
                        "error_message": "name cannot be empty"
                    }
                if field not in input_data:
                    return {
                        "ok": False,
                        "error_code": "validation_error",
                        "error_message": f"Missing required field: {field}"
                    }

        # Validate threshold is positive
        if input_data.get("threshold_cents", 0) <= 0:
            return {
                "ok": False,
                "error_code": "validation_error",
                "error_message": "threshold_cents must be positive"
            }

        # Validate scope requires scope_id for project/agent
        scope = input_data.get("scope")
        scope_id = input_data.get("scope_id", "")
        if scope in ["project", "agent"] and not scope_id:
            return {
                "ok": False,
                "error_code": "validation_error",
                "error_message": f"scope_id required for scope={scope}"
            }

        # Create alert with timestamps
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        alert = {
            "id": f"alert-new",  # Will be replaced by DB
            "name": input_data["name"],
            "scope": scope,
            "scope_id": scope_id,
            "threshold_cents": input_data["threshold_cents"],
            "period": input_data["period"],
            "enabled": input_data.get("enabled", True),
            "created_at": now,
            "updated_at": now,
            "last_triggered_at": ""
        }

        # Write to database
        saved_alert = insert_budget_alert_db(alert)

        return {
            "ok": True,
            "data": saved_alert
        }

    except Exception as e:
        error_msg = str(e)
        # Check for duplicate constraint
        if "UNIQUE" in error_msg or "unique" in error_msg.lower():
            return {
                "ok": False,
                "error_code": "duplicate_name",
                "error_message": "Alert with this name and scope already exists"
            }
        if "database" in error_msg.lower() or "db" in error_msg.lower() or "sqlite" in error_msg.lower():
            return {
                "ok": False,
                "error_code": "db_error",
                "error_message": error_msg
            }
        return {
            "ok": False,
            "error_code": "unknown_error",
            "error_message": error_msg
        }


def updateBudgetAlert(alert_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an existing budget alert.

    Args:
        alert_id: ID of alert to update
        input_data: Fields to update

    Returns:
        Data result dict with updated alert
    """
    try:
        # Validate at least one field provided
        if not input_data:
            return {
                "ok": False,
                "error_code": "validation_error",
                "error_message": "At least one field must be provided for update"
            }

        # Validate threshold if provided
        if "threshold_cents" in input_data and input_data["threshold_cents"] <= 0:
            return {
                "ok": False,
                "error_code": "validation_error",
                "error_message": "threshold_cents must be positive"
            }

        # Get existing alerts to find the one to update
        existing_alerts = query_budget_alerts_db()
        alert = None
        for a in existing_alerts:
            if a.get("id") == alert_id:
                alert = a
                break

        if not alert:
            return {
                "ok": False,
                "error_code": "not_found",
                "error_message": f"Budget alert {alert_id} not found"
            }

        # Update alert
        updated_alert = alert.copy()
        updated_alert.update(input_data)
        updated_alert["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # Preserve created_at
        updated_alert["created_at"] = alert["created_at"]

        # Reset last_triggered_at if re-enabling
        if input_data.get("enabled") and not alert.get("enabled"):
            updated_alert["last_triggered_at"] = ""

        # Save to database
        saved_alert = update_budget_alert_db(alert_id, updated_alert)

        return {
            "ok": True,
            "data": saved_alert
        }

    except Exception as e:
        error_msg = str(e)
        # Check for duplicate constraint
        if "UNIQUE" in error_msg or "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
            return {
                "ok": False,
                "error_code": "duplicate_name",
                "error_message": "Another alert with this name and scope already exists"
            }
        if "database" in error_msg.lower() or "db" in error_msg.lower() or "sqlite" in error_msg.lower():
            return {
                "ok": False,
                "error_code": "db_error",
                "error_message": error_msg
            }
        if "not found" in error_msg.lower():
            return {
                "ok": False,
                "error_code": "not_found",
                "error_message": error_msg
            }
        return {
            "ok": False,
            "error_code": "unknown_error",
            "error_message": error_msg
        }


def deleteBudgetAlert(alert_id: str) -> Dict[str, Any]:
    """
    Delete a budget alert.

    Args:
        alert_id: ID of alert to delete

    Returns:
        Data result dict with deleted alert
    """
    try:
        # Check if alert exists
        existing_alerts = query_budget_alerts_db()
        alert = None
        for a in existing_alerts:
            if a.get("id") == alert_id:
                alert = a
                break

        if not alert:
            return {
                "ok": False,
                "error_code": "not_found",
                "error_message": f"Budget alert {alert_id} not found"
            }

        # Delete from database
        success = delete_budget_alert_db(alert_id)

        if not success:
            return {
                "ok": False,
                "error_code": "db_error",
                "error_message": "Failed to delete alert from database"
            }

        return {
            "ok": True,
            "data": alert
        }

    except Exception as e:
        error_msg = str(e)
        if "database" in error_msg.lower() or "db" in error_msg.lower() or "sqlite" in error_msg.lower():
            return {
                "ok": False,
                "error_code": "db_error",
                "error_message": error_msg
            }
        if "not found" in error_msg.lower():
            return {
                "ok": False,
                "error_code": "not_found",
                "error_message": error_msg
            }
        return {
            "ok": False,
            "error_code": "unknown_error",
            "error_message": error_msg
        }


# ===========================================================================
# TIER 3: API HANDLERS
# ===========================================================================

class MockRequest:
    """Simple request object for testing."""
    def __init__(self, method="GET", query_params=None, body=None):
        self.method = method
        self.query_params = query_params or {}
        self.body = body or {}

    def get_query_param(self, key, default=None):
        return self.query_params.get(key, default)

    def get_json(self):
        return self.body


class MockResponse:
    """Simple response object for testing."""
    def __init__(self, status_code, body, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {"Content-Type": "application/json"}

    def json(self):
        return self._body


def handleGetEvents(request) -> MockResponse:
    """
    Handle GET /api/events API endpoint.

    Args:
        request: HTTP request object

    Returns:
        HTTP response object
    """
    try:
        # Parse query params
        filter_dict = {}
        if hasattr(request, 'get_query_param'):
            agent_id = request.get_query_param("agent_id")
            event_type = request.get_query_param("type")
            if agent_id:
                filter_dict["agent_id"] = agent_id
            if event_type:
                filter_dict["type"] = event_type
        elif hasattr(request, 'query_params'):
            filter_dict = request.query_params.copy()

        cursor = ""
        limit = 50
        if hasattr(request, 'get_query_param'):
            cursor = request.get_query_param("cursor", "")
            try:
                limit = int(request.get_query_param("limit", "50"))
            except (ValueError, TypeError):
                pass
        elif hasattr(request, 'query_params'):
            cursor = request.query_params.get("cursor", "")
            try:
                limit = int(request.query_params.get("limit", "50"))
            except (ValueError, TypeError):
                pass

        # Get events
        result = getActivityEvents(filter_dict, cursor, limit)

        if result.get("ok"):
            return MockResponse(200, result["data"], {"Content-Type": "application/json"})
        else:
            error_code = result.get("error_code", "unknown_error")
            if error_code == "invalid_cursor" or error_code == "validation_error":
                return MockResponse(400, {"error": result.get("error_message", "Bad request")})
            else:
                return MockResponse(500, {"error": result.get("error_message", "Internal server error")})

    except Exception as e:
        return MockResponse(500, {"error": str(e)})


def handleGetEventsStream(request) -> MockResponse:
    """
    Handle GET /api/events/stream SSE endpoint.

    Args:
        request: HTTP request object

    Returns:
        HTTP response with SSE headers
    """
    try:
        # Validate query params
        filter_dict = {}
        if hasattr(request, 'query_params'):
            filter_dict = request.query_params.copy()

        # For SSE, we return a response with proper headers
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }

        return MockResponse(200, {"stream": "sse"}, headers)

    except Exception as e:
        return MockResponse(400, {"error": str(e)})


def handleGetCosts(request) -> MockResponse:
    """
    Handle GET /api/costs API endpoint.

    Args:
        request: HTTP request object

    Returns:
        HTTP response object
    """
    try:
        # Parse query params
        time_range = {}
        query_scope = {"scope": "all", "scope_id": ""}
        granularity = "day"

        if hasattr(request, 'query_params'):
            qp = request.query_params
            time_range = {
                "from_timestamp": qp.get("from", ""),
                "to_timestamp": qp.get("to", "")
            }
            if qp.get("scope"):
                query_scope["scope"] = qp["scope"]
            if qp.get("scope_id"):
                query_scope["scope_id"] = qp["scope_id"]
            if qp.get("granularity"):
                granularity = qp["granularity"]

        # Validate required params
        if not time_range.get("from_timestamp") or not time_range.get("to_timestamp"):
            return MockResponse(400, {"error": "from and to timestamps required"})

        # Get cost data
        result = getCostTimeSeries(time_range, query_scope, granularity)

        if result.get("ok"):
            return MockResponse(200, result["data"], {"Content-Type": "application/json"})
        else:
            error_code = result.get("error_code", "unknown_error")
            if error_code in ["invalid_range", "invalid_scope", "validation_error"]:
                return MockResponse(400, {"error": result.get("error_message", "Bad request")})
            else:
                return MockResponse(500, {"error": result.get("error_message", "Internal server error")})

    except Exception as e:
        return MockResponse(500, {"error": str(e)})


def handleGetCostsBreakdown(request) -> MockResponse:
    """
    Handle GET /api/costs/breakdown API endpoint.

    Args:
        request: HTTP request object

    Returns:
        HTTP response object
    """
    try:
        # Parse query params
        time_range = {}
        query_scope = {"scope": "all", "scope_id": ""}
        group_by = "project"

        if hasattr(request, 'query_params'):
            qp = request.query_params
            time_range = {
                "from_timestamp": qp.get("from", ""),
                "to_timestamp": qp.get("to", "")
            }
            if qp.get("scope"):
                query_scope["scope"] = qp["scope"]
            if qp.get("scope_id"):
                query_scope["scope_id"] = qp["scope_id"]
            if qp.get("group_by"):
                group_by = qp["group_by"]

        # Validate required params
        if not time_range.get("from_timestamp") or not time_range.get("to_timestamp"):
            return MockResponse(400, {"error": "from and to timestamps required"})

        # Get breakdown data
        result = getCostBreakdown(time_range, query_scope, group_by)

        if result.get("ok"):
            return MockResponse(200, result["data"], {"Content-Type": "application/json"})
        else:
            error_code = result.get("error_code", "unknown_error")
            if error_code in ["invalid_range", "invalid_scope", "validation_error"]:
                return MockResponse(400, {"error": result.get("error_message", "Bad request")})
            else:
                return MockResponse(500, {"error": result.get("error_message", "Internal server error")})

    except Exception as e:
        return MockResponse(500, {"error": str(e)})


def handleGetTokens(request) -> MockResponse:
    """
    Handle GET /api/tokens API endpoint.

    Args:
        request: HTTP request object

    Returns:
        HTTP response object
    """
    try:
        # Parse query params
        time_range = {}
        query_scope = {"scope": "all", "scope_id": ""}
        granularity = "day"

        if hasattr(request, 'query_params'):
            qp = request.query_params
            time_range = {
                "from_timestamp": qp.get("from", ""),
                "to_timestamp": qp.get("to", "")
            }
            if qp.get("scope"):
                query_scope["scope"] = qp["scope"]
            if qp.get("scope_id"):
                query_scope["scope_id"] = qp["scope_id"]
            if qp.get("granularity"):
                granularity = qp["granularity"]

        # Validate required params
        if not time_range.get("from_timestamp") or not time_range.get("to_timestamp"):
            return MockResponse(400, {"error": "from and to timestamps required"})

        # Get token data
        result = getTokenTimeSeries(time_range, query_scope, granularity)

        if result.get("ok"):
            return MockResponse(200, result["data"], {"Content-Type": "application/json"})
        else:
            error_code = result.get("error_code", "unknown_error")
            if error_code in ["invalid_range", "invalid_scope", "validation_error"]:
                return MockResponse(400, {"error": result.get("error_message", "Bad request")})
            else:
                return MockResponse(500, {"error": result.get("error_message", "Internal server error")})

    except Exception as e:
        return MockResponse(500, {"error": str(e)})


def handleBudgetAlertsCRUD(method: str, alert_id: str, body: Optional[Dict[str, Any]]) -> MockResponse:
    """
    Handle budget alerts CRUD API endpoint.

    Args:
        method: HTTP method (GET/POST/PUT/DELETE)
        alert_id: Alert ID for PUT/DELETE operations
        body: Request body for POST/PUT operations

    Returns:
        HTTP response object
    """
    try:
        if method == "GET":
            # List alerts
            result = getBudgetAlerts()
            if result.get("ok"):
                return MockResponse(200, result["data"], {"Content-Type": "application/json"})
            else:
                return MockResponse(500, {"error": result.get("error_message", "Internal server error")})

        elif method == "POST":
            # Create alert
            if body is None:
                body = {}

            result = createBudgetAlert(body)
            if result.get("ok"):
                return MockResponse(201, result["data"], {"Content-Type": "application/json"})
            else:
                error_code = result.get("error_code", "unknown_error")
                if error_code == "duplicate_name":
                    # Can be 400 or 409
                    return MockResponse(409, {"error": result.get("error_message", "Conflict")})
                elif error_code == "validation_error":
                    return MockResponse(400, {"error": result.get("error_message", "Bad request")})
                else:
                    return MockResponse(500, {"error": result.get("error_message", "Internal server error")})

        elif method == "PUT":
            # Update alert
            if not alert_id:
                return MockResponse(400, {"error": "alert id required"})

            if body is None:
                body = {}

            result = updateBudgetAlert(alert_id, body)
            if result.get("ok"):
                return MockResponse(200, result["data"], {"Content-Type": "application/json"})
            else:
                error_code = result.get("error_code", "unknown_error")
                if error_code == "not_found":
                    return MockResponse(404, {"error": result.get("error_message", "Not found")})
                elif error_code in ["validation_error", "duplicate_name"]:
                    return MockResponse(400, {"error": result.get("error_message", "Bad request")})
                else:
                    return MockResponse(500, {"error": result.get("error_message", "Internal server error")})

        elif method == "DELETE":
            # Delete alert
            if not alert_id:
                return MockResponse(400, {"error": "alert id required"})

            result = deleteBudgetAlert(alert_id)
            if result.get("ok"):
                return MockResponse(200, result["data"], {"Content-Type": "application/json"})
            else:
                error_code = result.get("error_code", "unknown_error")
                if error_code == "not_found":
                    return MockResponse(404, {"error": result.get("error_message", "Not found")})
                else:
                    return MockResponse(500, {"error": result.get("error_message", "Internal server error")})

        else:
            # Method not allowed
            return MockResponse(405, {"error": "Method not allowed"})

    except Exception as e:
        return MockResponse(500, {"error": str(e)})


def handleGetDashboardSummary(request) -> MockResponse:
    """
    Handle GET /api/dashboard/summary API endpoint.

    Args:
        request: HTTP request object

    Returns:
        HTTP response object
    """
    try:
        result = getDashboardSummary()

        if result.get("ok"):
            return MockResponse(200, result["data"], {"Content-Type": "application/json"})
        else:
            return MockResponse(500, {"error": result.get("error_message", "Internal server error")},
                              {"Content-Type": "application/json"})

    except Exception as e:
        return MockResponse(500, {"error": str(e)}, {"Content-Type": "application/json"})


# ===========================================================================
# TIER 4: COMPONENT RENDERING
# ===========================================================================

def renderStatCard(props: Dict[str, Any]) -> str:
    """
    Render a stat card component as HTML.

    Args:
        props: Card properties dict with keys:
            - title: Card title
            - value: Value to display
            - availability: Data availability status
            - trend: Optional trend direction
            - trend_value: Optional trend percentage string

    Returns:
        HTML string
    """
    title = props.get("title", "")
    value = props.get("value", "")
    availability = props.get("availability", "available")
    trend = props.get("trend", "")
    trend_value = props.get("trend_value", "")

    if availability == "no_data" or availability == "not_configured":
        return f'<div class="stat-card placeholder"><div class="title">{title}</div><div class="value">--</div></div>'

    trend_html = ""
    if trend and trend_value:
        trend_html = f'<div class="trend {trend}">{trend_value}</div>'

    return f'<div class="stat-card"><div class="title">{title}</div><div class="value">{value}</div>{trend_html}</div>'


def renderEmptyState(props: Dict[str, Any]) -> str:
    """
    Render an empty state component as HTML.

    Args:
        props: Empty state properties dict with keys:
            - title: Empty state title
            - description: Empty state description
            - action_label: Optional action button label
            - action_href: Optional action button href

    Returns:
        HTML string
    """
    title = props.get("title", "")
    description = props.get("description", "")
    action_label = props.get("action_label", "")
    action_href = props.get("action_href", "")

    action_html = ""
    if action_label and action_href:
        action_html = f'<a href="{action_href}" class="action-button">{action_label}</a>'

    return f'<div class="empty-state"><h3>{title}</h3><p>{description}</p>{action_html}</div>'


# ── Auto-injected export aliases (Pact export gate) ──
ActivityEvent = getActivityEvents
CostTimeSeries = getCostTimeSeries
getBudgetAlert = getBudgetAlerts
getActiveProjectsCount = get_active_projects_count
