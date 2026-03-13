# === End-to-End & Integration Tests (e2e_tests) v1 ===
#  Dependencies: api_routes, data_access_layer, sse_event_bus, pact_integration, openclaw_reader, sqlite_database
# Playwright e2e test suite and API integration tests for OpenClaw Mission Control. Covers: login flow, overview page load (<2s), agent list rendering, project CRUD flow, task board interactions (create, move, assign), PACT pipeline view for fixture projects, activity feed SSE updates, and cost page rendering. All tests run against fixture data (mock openclaw.json, mock PACT directories, seeded SQLite) — no running OpenClaw instance or PACT daemon required. Targets Chromium at minimum with Firefox and WebKit configs. Includes integration tests for all API routes with Zod schema validation of responses.

# Module invariants:
#   - All tests run against fixture data only — no running OpenClaw instance or PACT daemon required
#   - No test may import or require openclaw or pact as direct library dependencies
#   - All API response assertions validate against the same Zod schemas used in production route handlers
#   - All error responses conform to the StandardApiError shape with a typed ErrorCode
#   - Database state is isolated per Playwright worker via per-worker database copies
#   - Global setup must complete before any test worker starts
#   - Global teardown must run even if tests fail (best-effort cleanup)
#   - E2e tests use Page Object Models for all page interactions — no raw selectors in test bodies
#   - Performance-tagged tests (@performance) run only in Chromium project
#   - PACT file parsers must handle missing or malformed files gracefully — never crash on bad data
#   - SSE integration tests must verify both event format and payload schema
#   - All factory functions produce valid fixture objects that pass their own Zod schemas
#   - Test fixtures are read-only during test execution — mutations go through API routes to the worker database
#   - Chromium browser project is always required; Firefox and WebKit are optional in local dev
#   - Tests must not depend on execution order — each test is independently runnable
#   - No duplicate type definitions — all types imported from lib/types/ or defined in this test component
#   - Files must stay under 250 lines per project standards; test helpers and POMs split into separate modules

class BrowserProject(Enum):
    """Supported Playwright browser projects for cross-browser testing"""
    chromium = "chromium"
    firefox = "firefox"
    webkit = "webkit"

class TestTag(Enum):
    """Tags for categorizing and filtering test runs"""
    e2e = "e2e"
    integration = "integration"
    performance = "performance"
    sse = "sse"
    crud = "crud"
    smoke = "smoke"
    regression = "regression"

class TestStatus(Enum):
    """Possible outcomes of a test execution"""
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    timed_out = "timed_out"
    interrupted = "interrupted"

class ErrorCode(Enum):
    """Typed error codes returned by API routes, used for assertion in integration tests"""
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    BAD_REQUEST = "BAD_REQUEST"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

class SSEEventType(Enum):
    """Types of events emitted over the SSE event stream"""
    agent_update = "agent_update"
    task_update = "task_update"
    project_update = "project_update"
    pact_update = "pact_update"
    activity = "activity"

class StandardApiError:
    """Standardized API error response shape validated by integration tests"""
    error: str                               # required, Human-readable error message
    code: ErrorCode                          # required, Typed error code for programmatic handling
    details: any = null                      # optional, Optional additional error context (validation errors, etc.)

class StandardApiResponse:
    """Generic wrapper for successful API responses validated in integration tests"""
    data: any                                # required, Response payload, validated against endpoint-specific Zod schema
    status: int                              # required, HTTP status code
    ok: bool                                 # required, Whether the response indicates success (2xx)

class FixtureConfig:
    """Configuration for test fixture directory layout and data sources"""
    openclaw_config_path: str                # required, Path to mock openclaw.json fixture file
    pact_directory_path: str                 # required, Path to mock PACT directory tree with pipeline.json and sessions
    db_seed_path: str                        # required, Path to SQLite seed SQL file
    db_schema_path: str                      # required, Path to SQLite schema SQL file (may import from lib/db/)
    temp_directory: str                      # required, Temp directory for isolated fixture copies per test worker
    responses_snapshot_path: str = None      # optional, Optional path to expected API response snapshots

class TestEnvironment:
    """Runtime test environment configuration resolved during global setup"""
    base_url: str                            # required, regex(^https?://), Base URL of the Next.js dev/test server
    db_path: str                             # required, Path to the worker-isolated SQLite database file
    openclaw_config_path: str                # required, Path to the copied mock openclaw.json for this worker
    pact_directory_path: str                 # required, Path to the copied mock PACT directory for this worker
    worker_id: str                           # required, Playwright worker identifier for parallel isolation
    browser_project: BrowserProject          # required, Active browser project for this test run

class PageObjectModel:
    """Base structure for Page Object Models. Each POM wraps a Playwright Page and exposes typed actions and assertions."""
    page_url: str                            # required, Relative URL path for this page
    page_title: str                          # required, Expected page title or heading for load verification
    selectors: dict                          # required, Map of semantic names to CSS/test-id selectors used by this POM

class FixtureProject:
    """A project entity as seeded in fixture data"""
    id: str                                  # required, Unique project identifier
    name: str                                # required, length(1..256), Project display name
    description: str                         # required, Project description
    status: str                              # required, Project status (active, archived, etc.)
    created_at: str                          # required, ISO 8601 creation timestamp

class FixtureTask:
    """A task entity as seeded in fixture data"""
    id: str                                  # required, Unique task identifier
    project_id: str                          # required, Parent project ID
    title: str                               # required, length(1..512), Task title
    status: str                              # required, Task board column (todo, in_progress, review, done)
    assigned_agent_id: str = None            # optional, Agent assigned to this task, if any
    priority: int                            # required, range(1..5), Task priority (1=highest, 5=lowest)

class FixtureAgent:
    """An agent entity as read from fixture openclaw.json"""
    id: str                                  # required, Unique agent identifier
    name: str                                # required, Agent display name
    role: str                                # required, Agent role (e.g., coder, reviewer, planner)
    status: str                              # required, Agent status (active, idle, offline)
    model: str                               # required, LLM model identifier used by the agent

class FixturePactPipeline:
    """A PACT pipeline as read from fixture PACT directory"""
    project_id: str                          # required, Project this pipeline belongs to
    stages: list                             # required, Ordered list of pipeline stages
    current_stage_index: int                 # required, range(0..100), Index of the currently active stage

class FixturePactStage:
    """A single stage in a PACT pipeline fixture"""
    name: str                                # required, Stage name (e.g., plan, act, check, transform)
    status: str                              # required, Stage status (pending, active, completed, failed)
    agent_id: str = None                     # optional, Agent responsible for this stage
    artifacts: list                          # required, File paths of artifacts produced by this stage

class SSETestEvent:
    """A parsed SSE event for assertion in integration tests"""
    event_type: SSEEventType                 # required, The SSE event name
    data: any                                # required, Parsed JSON payload of the event
    id: str = None                           # optional, Optional event ID for resumption
    timestamp_ms: int                        # required, Timestamp when the event was received (epoch ms)

class PerformanceMetrics:
    """Performance measurements captured during e2e performance tests"""
    page_load_ms: int                        # required, Wall-clock time from navigation start to page load complete
    first_contentful_paint_ms: int           # required, First Contentful Paint timing
    largest_contentful_paint_ms: int         # required, Largest Contentful Paint timing
    dom_content_loaded_ms: int               # required, DOMContentLoaded event timing
    content_visible_ms: int                  # required, Time until primary content selector becomes visible

class TestResult:
    """Result of a single test case execution"""
    test_name: str                           # required, Fully qualified test name
    status: TestStatus                       # required, Test outcome
    duration_ms: int                         # required, Test execution duration in milliseconds
    browser: BrowserProject                  # required, Browser the test ran on
    tags: list                               # required, Tags applied to this test
    error_message: str = None                # optional, Error message if test failed
    screenshot_path: str = None              # optional, Path to failure screenshot if captured

class TestSuiteResult:
    """Aggregate result of a full test suite run"""
    total: int                               # required, Total number of tests
    passed: int                              # required, Number of passed tests
    failed: int                              # required, Number of failed tests
    skipped: int                             # required, Number of skipped tests
    duration_ms: int                         # required, Total suite execution time
    results: list                            # required, Individual test results
    browsers_tested: list                    # required, Browsers that were included in this run

class ApiClientConfig:
    """Configuration for the typed HTTP client used in integration tests"""
    base_url: str                            # required, API base URL
    timeout_ms: int                          # required, range(1..60000), Request timeout in milliseconds
    headers: dict = None                     # optional, Default headers to include on all requests

class SSEClientConfig:
    """Configuration for the SSE test client used in integration tests"""
    url: str                                 # required, SSE endpoint URL
    timeout_ms: int                          # required, Connection timeout in milliseconds
    event_filter: list = None                # optional, Optional filter to subscribe to specific event types only
    max_events: int                          # required, range(1..10000), Maximum number of events to collect before auto-disconnect

def globalSetup(
    fixture_config: FixtureConfig,
) -> TestEnvironment:
    """
    Playwright global setup function. Copies fixture files to a temp directory, creates and seeds SQLite database from schema and seed SQL, sets environment variables pointing the Next.js test server at fixture data. Runs once before all test workers.

    Preconditions:
      - Fixture files exist at configured paths (openclaw.json, pact/, seed.sql, schema.sql)
      - Temp directory parent is writable
      - No prior test environment is active (clean state)

    Postconditions:
      - Temp directory created with copies of all fixture files
      - SQLite database created, schema applied, and seed data inserted
      - Environment variables OPENCLAW_CONFIG_PATH, PACT_DIR, DATABASE_PATH are set
      - TestEnvironment returned with all paths resolved

    Errors:
      - fixture_not_found (FileNotFoundError): Any configured fixture file or directory does not exist
      - db_schema_error (DatabaseSchemaError): Schema SQL is invalid or fails to execute
      - db_seed_error (DatabaseSeedError): Seed SQL fails (constraint violation, syntax error)
      - temp_dir_creation_failed (FilesystemError): Cannot create temp directory (permissions, disk space)

    Side effects: none
    Idempotent: no
    """
    ...

def globalTeardown(
    environment: TestEnvironment,
) -> None:
    """
    Playwright global teardown function. Removes temp directories, closes database connections, and cleans up environment variables. Runs once after all test workers complete.

    Preconditions:
      - globalSetup completed successfully and returned a valid TestEnvironment

    Postconditions:
      - Temp directory and all contents deleted
      - SQLite database file removed
      - Environment variables unset
      - No orphaned file handles or processes

    Errors:
      - cleanup_failed (FilesystemError): Cannot remove temp directory (file locked, permissions)
          note: Should log warning but not throw — teardown must be best-effort

    Side effects: none
    Idempotent: no
    """
    ...

def createWorkerDatabase(
    source_db_path: str,
    worker_id: str,
) -> str:
    """
    Creates a per-worker copy of the seeded SQLite database to ensure parallel test isolation. Each Playwright worker gets its own database file.

    Preconditions:
      - Source database file exists and is a valid SQLite database
      - Worker ID is non-empty and filesystem-safe

    Postconditions:
      - New database file created at a worker-specific path
      - Database is a byte-for-byte copy of the source
      - Returned string is the absolute path to the worker database

    Errors:
      - source_db_not_found (FileNotFoundError): Source database file does not exist
      - copy_failed (FilesystemError): Failed to copy database file (disk space, permissions)

    Side effects: none
    Idempotent: no
    """
    ...

def seedDatabase(
    db_path: str,
    schema_sql: str,
    seed_sql: str,
) -> None:
    """
    Applies schema and seed data to a SQLite database file. Used by global setup and can be called in individual tests for reset.

    Preconditions:
      - db_path parent directory exists and is writable
      - schema_sql contains valid SQLite DDL
      - seed_sql references only tables defined in schema_sql

    Postconditions:
      - Database file created or overwritten at db_path
      - All schema tables exist
      - All seed data rows are inserted
      - Database is in WAL mode for concurrent read support

    Errors:
      - schema_invalid (DatabaseSchemaError): Schema SQL contains syntax errors or invalid statements
      - seed_constraint_violation (DatabaseSeedError): Seed data violates schema constraints (FK, UNIQUE, NOT NULL)
      - db_write_failed (FilesystemError): Cannot write to database path

    Side effects: none
    Idempotent: no
    """
    ...

def resetDatabase(
    db_path: str,
    schema_sql: str,
    seed_sql: str,
) -> None:
    """
    Resets a worker database to its seeded state by dropping all tables and re-applying schema and seed data. Used between tests that mutate data.

    Preconditions:
      - Database file exists at db_path
      - No active transactions or open connections from other processes

    Postconditions:
      - All existing tables dropped
      - Schema and seed data re-applied cleanly
      - Database state identical to post-seedDatabase state

    Errors:
      - db_not_found (FileNotFoundError): Database file does not exist at db_path
      - db_locked (DatabaseLockError): Database is locked by another process
      - reset_failed (DatabaseSchemaError): Schema or seed re-application fails

    Side effects: none
    Idempotent: no
    """
    ...

def createFixtureProject(
    overrides: dict = None,
) -> FixtureProject:
    """
    Factory function to create a FixtureProject with sensible defaults. Used in test factories for generating test data.

    Postconditions:
      - Returned FixtureProject has all required fields populated
      - ID is a valid unique identifier (UUID format)
      - created_at is a valid ISO 8601 timestamp
      - Any overridden fields use the provided values

    Errors:
      - invalid_override_field (ValidationError): Override contains a field name not in FixtureProject

    Side effects: none
    Idempotent: no
    """
    ...

def createFixtureTask(
    project_id: str,
    overrides: dict = None,
) -> FixtureTask:
    """
    Factory function to create a FixtureTask with sensible defaults. Used in test factories for generating test data.

    Preconditions:
      - project_id is non-empty

    Postconditions:
      - Returned FixtureTask has all required fields populated
      - project_id matches the provided value
      - Default status is 'todo'
      - Default priority is 3

    Errors:
      - empty_project_id (ValidationError): project_id is empty string
      - invalid_override_field (ValidationError): Override contains a field name not in FixtureTask

    Side effects: none
    Idempotent: no
    """
    ...

def createFixtureAgent(
    overrides: dict = None,
) -> FixtureAgent:
    """
    Factory function to create a FixtureAgent with sensible defaults. Used in test factories for generating test data.

    Postconditions:
      - Returned FixtureAgent has all required fields populated
      - Default role is 'coder'
      - Default status is 'active'
      - Default model is 'claude-sonnet-4-20250514'

    Errors:
      - invalid_override_field (ValidationError): Override contains a field name not in FixtureAgent

    Side effects: none
    Idempotent: no
    """
    ...

def createFixturePactPipeline(
    project_id: str,
    overrides: dict = None,
) -> FixturePactPipeline:
    """
    Factory function to create a FixturePactPipeline with the standard PACT stages (Plan, Act, Check, Transform) and sensible defaults.

    Preconditions:
      - project_id is non-empty

    Postconditions:
      - Pipeline has at least 4 stages (plan, act, check, transform)
      - current_stage_index is within bounds of stages array
      - project_id matches the provided value

    Errors:
      - empty_project_id (ValidationError): project_id is empty string

    Side effects: none
    Idempotent: no
    """
    ...

def setupFixtureDirectories(
    temp_dir: str,
    pipelines: list,
    agents: list,
) -> FixtureConfig:
    """
    Creates the mock PACT directory tree structure in the temp directory with pipeline.json and session files for fixture projects.

    Preconditions:
      - temp_dir exists and is writable
      - pipelines list is non-empty
      - agents list is non-empty

    Postconditions:
      - openclaw.json written at temp_dir/openclaw.json with serialized agents
      - PACT directories created at temp_dir/pact/<project_id>/ for each pipeline
      - pipeline.json written in each project directory
      - sessions/ subdirectory created in each project directory
      - Returned FixtureConfig has all paths correctly set

    Errors:
      - temp_dir_not_found (FileNotFoundError): temp_dir does not exist
      - write_failed (FilesystemError): Cannot write files to temp_dir (permissions, disk space)
      - serialization_error (SerializationError): Pipeline or agent data cannot be serialized to JSON

    Side effects: none
    Idempotent: no
    """
    ...

def createApiClient(
    config: ApiClientConfig,
) -> dict:
    """
    Creates a typed HTTP client for API integration tests. Uses native fetch. Validates responses against Zod schemas from lib/types/.

    Preconditions:
      - config.base_url is a valid HTTP(S) URL
      - config.timeout_ms is positive

    Postconditions:
      - Returned dict contains methods: get, post, put, delete
      - Each method accepts path (str) and optional body (dict), returns StandardApiResponse
      - All responses are validated against StandardApiResponse or StandardApiError shape
      - Timeout is enforced via AbortController

    Errors:
      - invalid_base_url (ValidationError): base_url is not a valid URL
      - connection_refused (ConnectionError): Server is not running at base_url
      - timeout (TimeoutError): Request exceeds configured timeout_ms

    Side effects: none
    Idempotent: no
    """
    ...

def createSSEClient(
    config: SSEClientConfig,
) -> dict:
    """
    Creates a fetch-based SSE client for integration testing of the /api/events endpoint. Parses event stream, type-checks payloads against SSETestEvent schema, and collects events until max_events or timeout.

    Preconditions:
      - config.url is a valid HTTP(S) URL pointing to the SSE endpoint
      - config.timeout_ms is positive

    Postconditions:
      - Returned dict contains methods: connect, disconnect, waitForEvent, collectEvents, getReceivedEvents
      - connect() establishes SSE connection and begins collecting events
      - waitForEvent(eventType, timeout) resolves with the first matching SSETestEvent or rejects on timeout
      - collectEvents(count, timeout) resolves with an array of SSETestEvent when count events received or timeout
      - getReceivedEvents() returns all collected SSETestEvent objects
      - disconnect() closes the connection and stops collection

    Errors:
      - connection_failed (ConnectionError): Cannot establish SSE connection to the endpoint
      - timeout (TimeoutError): Timeout exceeded while waiting for events
      - invalid_event_payload (ValidationError): Received event data fails Zod schema validation
      - stream_closed_unexpectedly (StreamClosedError): Server closes SSE stream before expected events received

    Side effects: none
    Idempotent: no
    """
    ...

def runE2EOverviewPageTest(
    environment: TestEnvironment,
) -> TestResult:
    """
    E2e test: Navigates to the overview/home page, asserts it loads within 2000ms (AC1), verifies key dashboard widgets are rendered (agent summary, project list, activity feed preview, cost summary). Tagged @performance @smoke.

    Preconditions:
      - Next.js test server is running at environment.base_url
      - Fixture data is loaded (agents, projects, tasks)
      - Browser context is initialized

    Postconditions:
      - Overview page loaded and primary content visible within 2000ms
      - Agent summary widget displays correct count from fixture data
      - Project list shows seeded projects
      - Activity feed preview shows recent entries
      - Cost summary widget renders without error
      - TestResult captures PerformanceMetrics

    Errors:
      - page_load_timeout (TimeoutError): Page does not load within 30s navigation timeout
      - performance_assertion_failed (PerformanceAssertionError): Content not visible within 2000ms
      - widget_not_rendered (AssertionError): One or more dashboard widgets not found in DOM
      - data_mismatch (AssertionError): Rendered data does not match fixture data

    Side effects: none
    Idempotent: no
    """
    ...

def runE2ELoginFlowTest(
    environment: TestEnvironment,
) -> TestResult:
    """
    E2e test: Tests the login flow including form rendering, input validation, successful login, and redirect to dashboard. Verifies auth state persists across navigation.

    Preconditions:
      - Next.js test server is running
      - Login page is accessible
      - No existing auth session

    Postconditions:
      - Login form renders with email and password fields
      - Invalid input shows validation errors
      - Valid credentials redirect to dashboard
      - Auth cookie/token is set after successful login
      - Subsequent navigation retains authenticated state

    Errors:
      - login_form_not_rendered (AssertionError): Login form elements not found in DOM
      - validation_not_shown (AssertionError): Invalid input does not trigger visible validation errors
      - redirect_failed (AssertionError): Successful login does not redirect to dashboard
      - auth_not_persisted (AssertionError): Auth state lost on subsequent navigation

    Side effects: none
    Idempotent: no
    """
    ...

def runE2EAgentListTest(
    environment: TestEnvironment,
    expected_agents: list,
) -> TestResult:
    """
    E2e test: Navigates to the agents page, verifies all fixture agents are rendered with correct names, roles, statuses, and model info. Tests filtering and sorting if available.

    Preconditions:
      - Next.js test server is running
      - Fixture openclaw.json has been loaded with agent data
      - User is authenticated

    Postconditions:
      - Agent list page renders without errors
      - Each expected agent appears with correct name, role, status, and model
      - Agent count matches expected_agents length
      - Agent status indicators use correct visual styling (colors, icons)

    Errors:
      - agent_list_empty (AssertionError): Agent list renders but shows no agents
      - agent_data_mismatch (AssertionError): Rendered agent data does not match fixture data
      - missing_agent (AssertionError): One or more expected agents not found in rendered list

    Side effects: none
    Idempotent: no
    """
    ...

def runE2EProjectCRUDTest(
    environment: TestEnvironment,
    new_project: FixtureProject,
) -> TestResult:
    """
    E2e test: Tests the full project CRUD lifecycle through the UI — create a new project, verify it appears in the list, edit its name and description, verify changes persist, delete it, and verify removal. Covers AC for project management.

    Preconditions:
      - Next.js test server is running
      - User is authenticated
      - Database is in seeded state

    Postconditions:
      - Create: New project form submits successfully, project appears in list
      - Read: Project detail page shows correct name, description, status
      - Update: Edit form saves changes, list reflects updated name/description
      - Delete: Confirmation dialog shown, project removed from list after confirm
      - Database state reflects all CRUD operations

    Errors:
      - create_form_error (AssertionError): Project creation form fails to submit or shows unexpected error
      - project_not_in_list (AssertionError): Created project does not appear in project list
      - edit_not_persisted (AssertionError): Edited project fields revert on page reload
      - delete_not_confirmed (AssertionError): Delete confirmation dialog not shown
      - project_not_removed (AssertionError): Deleted project still appears in list

    Side effects: none
    Idempotent: no
    """
    ...

def runE2ETaskBoardTest(
    environment: TestEnvironment,
    project_id: str,
    new_task: FixtureTask,
) -> TestResult:
    """
    E2e test: Tests task board interactions — create a task, move it between columns (todo → in_progress → review → done) via drag-and-drop or UI controls, assign it to an agent, verify visual updates. Covers AC for task board.

    Preconditions:
      - Next.js test server is running
      - User is authenticated
      - Project with project_id exists in seeded data
      - At least one agent exists for assignment

    Postconditions:
      - Task created and visible in the 'todo' column
      - Task successfully moved to 'in_progress' column
      - Task successfully moved to 'review' column
      - Task successfully moved to 'done' column
      - Task assigned to an agent, agent avatar/name shown on task card
      - Task counts update in column headers
      - State persists on page reload

    Errors:
      - task_creation_failed (AssertionError): Task form submission fails or task not visible in board
      - drag_drop_failed (AssertionError): Drag and drop interaction does not move task to target column
      - assignment_failed (AssertionError): Agent assignment UI does not work or assignment not reflected
      - state_not_persisted (AssertionError): Task position or assignment lost on page reload

    Side effects: none
    Idempotent: no
    """
    ...

def runE2EPactPipelineTest(
    environment: TestEnvironment,
    expected_pipeline: FixturePactPipeline,
) -> TestResult:
    """
    E2e test: Navigates to the PACT pipeline view for a fixture project, verifies all pipeline stages are rendered with correct names and statuses, verifies active stage is visually highlighted, and stage artifacts are listed. Tests fixture project-alpha pipeline.

    Preconditions:
      - Next.js test server is running
      - User is authenticated
      - PACT fixture directory exists with pipeline.json for the project

    Postconditions:
      - Pipeline view page renders without errors
      - All stages displayed in correct order with correct names
      - Each stage shows correct status (pending/active/completed/failed)
      - Active stage is visually distinguished (highlighted, expanded)
      - Stage artifacts listed for completed stages
      - Agent assignment shown for each stage

    Errors:
      - pipeline_not_rendered (AssertionError): Pipeline visualization component not found in DOM
      - stage_count_mismatch (AssertionError): Number of rendered stages does not match expected pipeline
      - stage_status_mismatch (AssertionError): One or more stages show incorrect status
      - active_stage_not_highlighted (AssertionError): Current active stage not visually distinguished

    Side effects: none
    Idempotent: no
    """
    ...

def runE2EActivityFeedSSETest(
    environment: TestEnvironment,
    trigger_task: FixtureTask,
) -> TestResult:
    """
    E2e test: Opens the activity feed page, triggers an action that generates an SSE event (e.g., creating a task via API), and verifies the activity feed updates in real-time without page reload. Tests SSE-driven live updates.

    Preconditions:
      - Next.js test server is running
      - User is authenticated
      - Activity feed page is accessible
      - SSE endpoint /api/events is operational

    Postconditions:
      - Activity feed page renders with existing activity entries
      - After task creation, new activity entry appears in feed without reload
      - New entry shows correct event type, timestamp, and description
      - Feed maintains chronological order (newest first)
      - SSE connection indicator shows connected status

    Errors:
      - feed_not_rendered (AssertionError): Activity feed component not found in DOM
      - sse_not_connected (AssertionError): SSE connection not established (no connection indicator)
      - live_update_not_received (TimeoutError): New activity entry does not appear within 5s of triggering action
      - entry_data_incorrect (AssertionError): New activity entry shows incorrect data

    Side effects: none
    Idempotent: no
    """
    ...

def runE2ECostPageTest(
    environment: TestEnvironment,
) -> TestResult:
    """
    E2e test: Navigates to the cost tracking page, verifies cost summary cards render with correct totals from fixture data, verifies recharts charts render (token usage, cost over time), and tests date range filtering if available.

    Preconditions:
      - Next.js test server is running
      - User is authenticated
      - Fixture data includes cost/token usage data

    Postconditions:
      - Cost page renders without errors
      - Summary cards show total cost, total tokens, cost per project
      - At least one recharts chart renders (SVG elements present)
      - Chart data points correspond to fixture data
      - No JavaScript errors in browser console

    Errors:
      - cost_page_error (AssertionError): Cost page fails to render or shows error boundary
      - charts_not_rendered (AssertionError): Recharts SVG elements not found in DOM
      - summary_data_mismatch (AssertionError): Cost summary values do not match fixture data

    Side effects: none
    Idempotent: no
    """
    ...

def runIntegrationProjectsAPITest(
    api_client: dict,
    test_project: FixtureProject,
) -> TestResult:
    """
    Integration test: Tests /api/projects CRUD operations. GET returns all projects, POST creates a project (validates Zod schema), PUT updates project fields, DELETE removes a project. Tests both success and error responses against StandardApiError schema.

    Preconditions:
      - API client is configured and connected
      - Database is in seeded state

    Postconditions:
      - GET /api/projects returns 200 with array of projects matching seed data
      - POST /api/projects with valid body returns 201 with created project
      - POST /api/projects with invalid body returns 400 with StandardApiError (VALIDATION_ERROR)
      - PUT /api/projects/:id with valid body returns 200 with updated project
      - PUT /api/projects/:nonexistent returns 404 with StandardApiError (NOT_FOUND)
      - DELETE /api/projects/:id returns 200 or 204
      - DELETE /api/projects/:nonexistent returns 404
      - All success responses validate against project Zod schema
      - All error responses validate against StandardApiError schema

    Errors:
      - unexpected_status_code (AssertionError): API returns unexpected HTTP status for a given operation
      - response_schema_mismatch (ValidationError): Response body does not match expected Zod schema
      - missing_error_code (AssertionError): Error response lacks required code field

    Side effects: none
    Idempotent: no
    """
    ...

def runIntegrationTasksAPITest(
    api_client: dict,
    test_task: FixtureTask,
    valid_project_id: str,
) -> TestResult:
    """
    Integration test: Tests /api/tasks CRUD operations. Validates task creation with project_id reference, status transitions, agent assignment, priority constraints, and error cases (invalid project_id, invalid status, etc.).

    Preconditions:
      - API client is configured
      - Database is in seeded state with at least one project and one agent

    Postconditions:
      - GET /api/tasks returns 200 with array of tasks
      - GET /api/tasks?project_id=X filters by project
      - POST /api/tasks with valid body returns 201
      - POST /api/tasks with invalid project_id returns 400 or 404
      - POST /api/tasks with priority outside 1-5 returns 400 (VALIDATION_ERROR)
      - PUT /api/tasks/:id status field changes persist
      - PUT /api/tasks/:id assigned_agent_id field changes persist
      - DELETE /api/tasks/:id returns 200 or 204
      - All responses validate against appropriate Zod schemas

    Errors:
      - fk_violation_not_caught (AssertionError): Invalid project_id accepted without error
      - validation_bypass (AssertionError): Invalid priority or status values accepted
      - response_schema_mismatch (ValidationError): Response body does not match expected Zod schema

    Side effects: none
    Idempotent: no
    """
    ...

def runIntegrationAgentsAPITest(
    api_client: dict,
    expected_agents: list,
) -> TestResult:
    """
    Integration test: Tests /api/agents read-only operations. GET returns all agents from fixture openclaw.json. GET /:id returns a single agent. Tests 404 for non-existent agent ID. Validates response against agent Zod schema.

    Preconditions:
      - API client is configured
      - Fixture openclaw.json is loaded with agent data

    Postconditions:
      - GET /api/agents returns 200 with array matching expected_agents count
      - Each agent in response has id, name, role, status, model fields
      - GET /api/agents/:validId returns 200 with matching agent
      - GET /api/agents/:nonexistent returns 404 with StandardApiError
      - Agent data matches fixture openclaw.json values exactly
      - All responses validate against agent Zod schema

    Errors:
      - agent_count_mismatch (AssertionError): Number of returned agents does not match expected
      - agent_data_mismatch (AssertionError): Agent fields do not match fixture data
      - missing_404_on_nonexistent (AssertionError): Non-existent agent ID does not return 404

    Side effects: none
    Idempotent: no
    """
    ...

def runIntegrationPactAPITest(
    api_client: dict,
    expected_pipeline: FixturePactPipeline,
) -> TestResult:
    """
    Integration test: Tests /api/pact read-only operations. GET /api/pact/pipelines returns all pipelines. GET /api/pact/pipelines/:projectId returns a specific pipeline. Tests graceful handling of missing/malformed pipeline.json files. Validates responses against PACT Zod schemas.

    Preconditions:
      - API client is configured
      - PACT fixture directory exists with at least one valid pipeline.json

    Postconditions:
      - GET /api/pact/pipelines returns 200 with array of pipelines
      - GET /api/pact/pipelines/:validProjectId returns 200 with pipeline matching expected_pipeline
      - GET /api/pact/pipelines/:nonexistent returns 404 with StandardApiError
      - Pipeline response includes stages array with correct order and status
      - Malformed pipeline.json returns 500 or 422 with descriptive error (never crashes server)
      - All valid responses validate against PACT pipeline Zod schema

    Errors:
      - pipeline_not_found (AssertionError): Valid project but missing pipeline.json returns wrong status
      - malformed_pipeline_crashes (AssertionError): Malformed pipeline.json causes server error instead of graceful 422/500
      - stage_order_wrong (AssertionError): Pipeline stages returned in wrong order
      - response_schema_mismatch (ValidationError): Response does not match PACT pipeline Zod schema

    Side effects: none
    Idempotent: no
    """
    ...

def runIntegrationSSEEndpointTest(
    sse_client_config: SSEClientConfig,
    api_client: dict,
) -> TestResult:
    """
    Integration test: Tests /api/events SSE endpoint. Verifies connection establishment, event stream format (event: type, data: JSON, id: optional), event filtering by type parameter, and graceful reconnection. Uses the fetch-based SSE test client.

    Preconditions:
      - Next.js test server is running with SSE endpoint active
      - Database is in seeded state

    Postconditions:
      - SSE connection established successfully (200 with text/event-stream content-type)
      - Connection sends proper SSE headers (Cache-Control: no-cache, Connection: keep-alive)
      - Triggered actions produce SSE events with correct type and data
      - Event data validates against SSETestEvent schema
      - Event filter parameter limits received events to specified types
      - Client disconnect is clean (no server errors)

    Errors:
      - connection_not_sse (AssertionError): Endpoint does not return text/event-stream content type
      - event_not_received (TimeoutError): Triggered action does not produce expected SSE event within timeout
      - event_format_invalid (AssertionError): SSE event does not follow event: / data: / id: format
      - filter_not_applied (AssertionError): Events of filtered-out types are still received
      - event_payload_invalid (ValidationError): Event data JSON does not validate against schema

    Side effects: none
    Idempotent: no
    """
    ...

def getPlaywrightConfig(
    ci_mode: bool,
    base_url: str = http://localhost:3000,
) -> dict:
    """
    Returns the Playwright configuration object. Defines multi-browser projects (Chromium required, Firefox and WebKit optional), webServer config pointing at Next.js dev server, global setup/teardown paths, test directory patterns, reporter config, and retry/timeout settings.

    Postconditions:
      - Returned config includes at least 'chromium' project
      - In CI mode, 'firefox' and 'webkit' projects are also included
      - webServer config starts Next.js on the specified port
      - Global setup points to tests/global-setup.ts
      - Global teardown points to tests/global-teardown.ts
      - Test match patterns include tests/e2e/**/*.spec.ts and tests/integration/**/*.spec.ts
      - Timeout set to 30s per test, navigation timeout 15s
      - Retries set to 2 in CI, 0 locally
      - Screenshot on failure enabled in CI

    Errors:
      - invalid_base_url (ValidationError): base_url is not a valid URL

    Side effects: none
    Idempotent: yes
    """
    ...

# ── REQUIRED EXPORTS ──────────────────────────────────
# Your implementation module MUST export ALL of these names
# with EXACTLY these spellings. Tests import them by name.
# __all__ = ['BrowserProject', 'TestTag', 'TestStatus', 'ErrorCode', 'SSEEventType', 'StandardApiError', 'StandardApiResponse', 'FixtureConfig', 'TestEnvironment', 'PageObjectModel', 'FixtureProject', 'FixtureTask', 'FixtureAgent', 'FixturePactPipeline', 'FixturePactStage', 'SSETestEvent', 'PerformanceMetrics', 'TestResult', 'TestSuiteResult', 'ApiClientConfig', 'SSEClientConfig', 'globalSetup', 'DatabaseSchemaError', 'DatabaseSeedError', 'FilesystemError', 'globalTeardown', 'createWorkerDatabase', 'seedDatabase', 'resetDatabase', 'DatabaseLockError', 'createFixtureProject', 'ValidationError', 'createFixtureTask', 'createFixtureAgent', 'createFixturePactPipeline', 'setupFixtureDirectories', 'SerializationError', 'createApiClient', 'ConnectionError', 'TimeoutError', 'createSSEClient', 'StreamClosedError', 'runE2EOverviewPageTest', 'PerformanceAssertionError', 'AssertionError', 'runE2ELoginFlowTest', 'runE2EAgentListTest', 'runE2EProjectCRUDTest', 'runE2ETaskBoardTest', 'runE2EPactPipelineTest', 'runE2EActivityFeedSSETest', 'runE2ECostPageTest', 'runIntegrationProjectsAPITest', 'runIntegrationTasksAPITest', 'runIntegrationAgentsAPITest', 'runIntegrationPactAPITest', 'runIntegrationSSEEndpointTest', 'getPlaywrightConfig']
