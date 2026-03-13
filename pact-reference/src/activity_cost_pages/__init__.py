"""
Activity Feed & Cost Tracking Pages module.

Exports all public functions for the dashboard's activity and cost tracking features.
"""

from .activity_cost_pages import (
    # Tier 1: Formatters
    formatCentsToCurrency,
    formatTokenCount,

    # Tier 2: Data Layer
    getActivityEvents,
    getCostTimeSeries,
    getCostBreakdown,
    getTokenTimeSeries,
    getDashboardSummary,
    getBudgetAlerts,
    createBudgetAlert,
    updateBudgetAlert,
    deleteBudgetAlert,

    # Tier 3: API Handlers
    handleGetEvents,
    handleGetEventsStream,
    handleGetCosts,
    handleGetCostsBreakdown,
    handleGetTokens,
    handleBudgetAlertsCRUD,
    handleGetDashboardSummary,

    # Tier 4: Components
    renderStatCard,
    renderEmptyState,

    # Internal functions (exported for testing/mocking)
    read_event_files,
    read_cost_files,
    query_budget_alerts_db,
    insert_budget_alert_db,
    update_budget_alert_db,
    delete_budget_alert_db,
    get_agent_summary,
    get_pact_health,
    get_active_projects_count,
)

__all__ = [
    "formatCentsToCurrency",
    "formatTokenCount",
    "getActivityEvents",
    "getCostTimeSeries",
    "getCostBreakdown",
    "getTokenTimeSeries",
    "getDashboardSummary",
    "getBudgetAlerts",
    "createBudgetAlert",
    "updateBudgetAlert",
    "deleteBudgetAlert",
    "handleGetEvents",
    "handleGetEventsStream",
    "handleGetCosts",
    "handleGetCostsBreakdown",
    "handleGetTokens",
    "handleBudgetAlertsCRUD",
    "handleGetDashboardSummary",
    "renderStatCard",
    "renderEmptyState",
    "read_event_files",
    "read_cost_files",
    "query_budget_alerts_db",
    "insert_budget_alert_db",
    "update_budget_alert_db",
    "delete_budget_alert_db",
    "get_agent_summary",
    "get_pact_health",
    "get_active_projects_count",
]
