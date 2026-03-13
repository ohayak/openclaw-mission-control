"""
Data Access Layer Package
Exposes all public functions and types.
"""

from .data_layer import (
    # Enums
    ErrorKind,
    AgentRole,
    AgentStatus,
    PipelinePhase,
    ContractStatus,
    TestResult,
    TaskStatus,
    TaskPriority,
    ActivityEventType,

    # Path validation
    validatePath,

    # Filesystem I/O
    readFileRaw,
    readDirectoryEntries,

    # Parsers
    parseOpenClawConfig,
    parsePactYaml,
    parsePactContract,
    parseSessionCostData,
    parseDecompositionTree,

    # Utilities
    derivePipelinePhase,

    # Facade - OpenClaw
    getOpenClawConfig,
    getAgent,
    listAgents,

    # Facade - PACT Projects
    getProject,
    listProjects,
    getProjectPipelineStatus,
    getProjectContracts,
    getProjectTestResults,
    getProjectComponentTree,

    # Facade - Cost & Activity
    getCostRecords,
    getCostSummary,
    getActivityFeed,

    # SQLite - Database
    initDatabase,
    closeDatabase,
    getAppliedMigrations,

    # SQLite - Tasks
    createTask,
    getTask,
    listTasks,
    updateTask,
    deleteTask,

    # SQLite - Preferences
    getUserPreferences,
    updateUserPreferences,

    # Cache
    invalidateCache,
    getCacheStats,
)

__all__ = [
    # Enums
    "ErrorKind",
    "AgentRole",
    "AgentStatus",
    "PipelinePhase",
    "ContractStatus",
    "TestResult",
    "TaskStatus",
    "TaskPriority",
    "ActivityEventType",

    # Path validation
    "validatePath",

    # Filesystem I/O
    "readFileRaw",
    "readDirectoryEntries",

    # Parsers
    "parseOpenClawConfig",
    "parsePactYaml",
    "parsePactContract",
    "parseSessionCostData",
    "parseDecompositionTree",

    # Utilities
    "derivePipelinePhase",

    # Facade - OpenClaw
    "getOpenClawConfig",
    "getAgent",
    "listAgents",

    # Facade - PACT Projects
    "getProject",
    "listProjects",
    "getProjectPipelineStatus",
    "getProjectContracts",
    "getProjectTestResults",
    "getProjectComponentTree",

    # Facade - Cost & Activity
    "getCostRecords",
    "getCostSummary",
    "getActivityFeed",

    # SQLite - Database
    "initDatabase",
    "closeDatabase",
    "getAppliedMigrations",

    # SQLite - Tasks
    "createTask",
    "getTask",
    "listTasks",
    "updateTask",
    "deleteTask",

    # SQLite - Preferences
    "getUserPreferences",
    "updateUserPreferences",

    # Cache
    "invalidateCache",
    "getCacheStats",
]
