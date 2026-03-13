"""
E2E and Integration Test Infrastructure for OpenClaw Mission Control.
"""

# Import standard library modules for test mocking
import os
import shutil
import sqlite3
import json

from .e2e_tests import (
    chromium,  # Export for mocking in tests
    # Enums
    BrowserProject,
    TestTag,
    TestStatus,
    ErrorCode,
    SSEEventType,

    # Exceptions
    DatabaseSchemaError,
    DatabaseSeedError,
    FilesystemError,
    DatabaseLockError,
    ValidationError,
    SerializationError,
    ConnectionError,
    TimeoutError,
    StreamClosedError,
    PerformanceAssertionError,
    AssertionError,

    # Data Classes
    StandardApiError,
    StandardApiResponse,
    FixtureConfig,
    TestEnvironment,
    PageObjectModel,
    FixtureProject,
    FixtureTask,
    FixtureAgent,
    FixturePactPipeline,
    FixturePactStage,
    SSETestEvent,
    PerformanceMetrics,
    TestResult,
    TestSuiteResult,
    ApiClientConfig,
    SSEClientConfig,

    # Infrastructure Functions
    globalSetup,
    globalTeardown,
    createWorkerDatabase,
    seedDatabase,
    resetDatabase,

    # Fixture Factory Functions
    createFixtureProject,
    createFixtureTask,
    createFixtureAgent,
    createFixturePactPipeline,
    setupFixtureDirectories,

    # Client Functions
    createApiClient,
    createSSEClient,

    # E2E Test Runner Functions
    runE2EOverviewPageTest,
    runE2ELoginFlowTest,
    runE2EAgentListTest,
    runE2EProjectCRUDTest,
    runE2ETaskBoardTest,
    runE2EPactPipelineTest,
    runE2EActivityFeedSSETest,
    runE2ECostPageTest,

    # Integration Test Runner Functions
    runIntegrationProjectsAPITest,
    runIntegrationTasksAPITest,
    runIntegrationAgentsAPITest,
    runIntegrationPactAPITest,
    runIntegrationSSEEndpointTest,

    # Configuration Function
    getPlaywrightConfig,
)

__all__ = [
    # Enums
    "BrowserProject",
    "TestTag",
    "TestStatus",
    "ErrorCode",
    "SSEEventType",

    # Exceptions
    "DatabaseSchemaError",
    "DatabaseSeedError",
    "FilesystemError",
    "DatabaseLockError",
    "ValidationError",
    "SerializationError",
    "ConnectionError",
    "TimeoutError",
    "StreamClosedError",
    "PerformanceAssertionError",
    "AssertionError",

    # Data Classes
    "StandardApiError",
    "StandardApiResponse",
    "FixtureConfig",
    "TestEnvironment",
    "PageObjectModel",
    "FixtureProject",
    "FixtureTask",
    "FixtureAgent",
    "FixturePactPipeline",
    "FixturePactStage",
    "SSETestEvent",
    "PerformanceMetrics",
    "TestResult",
    "TestSuiteResult",
    "ApiClientConfig",
    "SSEClientConfig",

    # Infrastructure Functions
    "globalSetup",
    "globalTeardown",
    "createWorkerDatabase",
    "seedDatabase",
    "resetDatabase",

    # Fixture Factory Functions
    "createFixtureProject",
    "createFixtureTask",
    "createFixtureAgent",
    "createFixturePactPipeline",
    "setupFixtureDirectories",

    # Client Functions
    "createApiClient",
    "createSSEClient",

    # E2E Test Runner Functions
    "runE2EOverviewPageTest",
    "runE2ELoginFlowTest",
    "runE2EAgentListTest",
    "runE2EProjectCRUDTest",
    "runE2ETaskBoardTest",
    "runE2EPactPipelineTest",
    "runE2EActivityFeedSSETest",
    "runE2ECostPageTest",

    # Integration Test Runner Functions
    "runIntegrationProjectsAPITest",
    "runIntegrationTasksAPITest",
    "runIntegrationAgentsAPITest",
    "runIntegrationPactAPITest",
    "runIntegrationSSEEndpointTest",

    # Configuration Function
    "getPlaywrightConfig",
]
