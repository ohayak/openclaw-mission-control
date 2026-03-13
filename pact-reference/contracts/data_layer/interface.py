# === Data Access Layer (Filesystem + SQLite) (data_layer) v1 ===
# The lib/data/ module that is the single gateway for all data access. Three-tier architecture: Tier 1 (lib/types/) defines domain types, Zod schemas, and Result<T> discriminated union. Tier 2 (lib/openclaw/, lib/pact/) provides internal parsers that separate I/O (read) from validation (parse) for testability. Tier 3 (lib/data/) is the public facade re-exporting domain-level functions with Map-based TTL caching. lib/db/ provides typed SQLite wrappers in WAL mode. All parsers return typed results with explicit error states. All filesystem access uses try-read-catch pattern (no existence checks). Base directories are always parameters for dependency injection in tests. Date strings use ISO 8601 format throughout. Naming convention: get* returns single item, list* returns arrays, create/update/delete mutate SQLite.

# Module invariants:
#   - Components and API routes MUST import only from lib/data/ facade — never from lib/openclaw/, lib/pact/, or lib/db/ directly
#   - All filesystem reads use try-read-catch-ENOENT pattern — never fs.existsSync or fs.access before reading
#   - All external data (files, CLI output) is validated through Zod .safeParse() before entering the domain
#   - All date/time values are represented as ISO 8601 strings (YYYY-MM-DDTHH:mm:ss.sssZ)
#   - All Result error variants carry the originating file path and original error message for debugging
#   - SQLite database operates in WAL mode for concurrent read performance
#   - Base directory paths are always function parameters — never hardcoded or read from env inside parsers
#   - Parse functions are pure (no I/O) and can be tested with inline fixture data
#   - Read functions are async and perform filesystem I/O, returning Result<unknown>
#   - No 'any' types — use 'unknown' + type narrowing via Zod
#   - Cache entries have explicit TTL and can be invalidated programmatically via invalidateCache
#   - File paths are validated to prevent directory traversal (no '..' components after resolution)
#   - All public facade functions are async, even if underlying implementation is synchronous, for API uniformity

class ErrorKind(Enum):
    """Finite union of error categories for all data access operations."""
    not_found = "not_found"
    malformed = "malformed"
    permission_denied = "permission_denied"
    io_error = "io_error"
    empty = "empty"

class DataError:
    """Structured error carrying context for debugging. Every failed Result includes one."""
    kind: ErrorKind                          # required, Category of the error.
    message: str                             # required, Human-readable error description.
    filePath: str                            # required, Absolute path of the file that caused the error, or empty string if not file-related.
    originalError: str                       # required, Stringified original error (e.g., ENOENT message, Zod error format output).

class ResultOk:
    """Success variant of the Result discriminated union."""
    ok: bool                                 # required, Always true for success variant.
    value: any                               # required, The successfully parsed/retrieved value. Actual type is generic T in implementation.

class ResultErr:
    """Error variant of the Result discriminated union."""
    ok: bool                                 # required, Always false for error variant.
    error: DataError                         # required, Structured error with context.

Result = ResultOk | ResultErr

class AgentRole(Enum):
    """Roles an agent can have in the OpenClaw system."""
    architect = "architect"
    developer = "developer"
    reviewer = "reviewer"
    tester = "tester"
    orchestrator = "orchestrator"
    custom = "custom"

class AgentStatus(Enum):
    """Current operational status of an agent."""
    idle = "idle"
    working = "working"
    error = "error"
    offline = "offline"
    unknown = "unknown"

class AgentDefinition:
    """An agent definition parsed from openclaw.json. Represents a configured AI agent."""
    id: str                                  # required, Unique agent identifier.
    name: str                                # required, Human-readable agent name.
    role: AgentRole                          # required, Agent's assigned role.
    model: str                               # required, LLM model identifier (e.g., 'claude-sonnet-4-20250514').
    status: AgentStatus                      # required, Current operational status.
    workspaceDir: str                        # required, Absolute path to agent's workspace directory.
    customRole: str = None                   # optional, Custom role description when role is 'custom'.
    lastActiveAt: str = None                 # optional, ISO 8601 timestamp of last activity, or empty if never active.
    configHash: str = None                   # optional, SHA-256 hash of the agent's config block for change detection.

AgentList = list[AgentDefinition]
# List of agent definitions.

class OpenClawConfig:
    """Top-level OpenClaw configuration parsed from openclaw.json."""
    version: str                             # required, Config file version string.
    projectName: str                         # required, Name of the OpenClaw project.
    agents: AgentList                        # required, All configured agents.
    baseDir: str                             # required, Resolved absolute base directory of the OpenClaw project.

class PipelinePhase(Enum):
    """Current phase of a PACT project pipeline, derived from directory contents."""
    not_started = "not_started"
    decomposition = "decomposition"
    contracting = "contracting"
    implementation = "implementation"
    testing = "testing"
    complete = "complete"
    unknown = "unknown"

class ContractStatus(Enum):
    """Status of a single PACT contract file."""
    draft = "draft"
    approved = "approved"
    implemented = "implemented"
    tested = "tested"
    missing = "missing"

class PactContract:
    """A single PACT contract and its current status."""
    componentId: str                         # required, Component identifier from the contract.
    name: str                                # required, Human-readable component name.
    filePath: str                            # required, Relative path to the contract file from project root.
    status: ContractStatus                   # required, Derived status of this contract.
    version: int                             # required, Contract version number.

PactContractList = list[PactContract]
# List of PACT contracts.

class TestResult(Enum):
    """Outcome of a test execution."""
    pass = "pass"
    fail = "fail"
    skip = "skip"
    error = "error"
    not_run = "not_run"

class PactTestSuite:
    """Aggregated test results for a PACT component."""
    componentId: str                         # required, Component this test suite covers.
    totalTests: int                          # required, Total number of tests.
    passed: int                              # required, Number of passing tests.
    failed: int                              # required, Number of failing tests.
    skipped: int                             # required, Number of skipped tests.
    errors: int                              # required, Number of tests that errored.
    lastRunAt: str                           # required, ISO 8601 timestamp of last test run, or empty if never run.

PactTestSuiteList = list[PactTestSuite]
# List of test suites.

class ComponentNode:
    """A node in the PACT component decomposition tree."""
    id: str                                  # required, Component identifier.
    name: str                                # required, Component display name.
    parentId: str                            # required, Parent component ID, or empty string for root.
    children: ComponentNodeList              # required, Child component nodes.
    contractStatus: ContractStatus           # required, Status of this component's contract.
    hasImplementation: bool                  # required, Whether source code exists in src/ for this component.
    hasTests: bool                           # required, Whether tests exist in tests/ for this component.

ComponentNodeList = list[ComponentNode]
# List of component tree nodes.

class PactProjectConfig:
    """Parsed pact.yaml configuration for a PACT project."""
    projectId: str                           # required, Unique project identifier.
    name: str                                # required, Project display name.
    description: str                         # required, Project description.
    createdAt: str                           # required, ISO 8601 creation timestamp.
    rootDir: str                             # required, Resolved absolute root directory of the PACT project.

class PactProjectSummary:
    """Aggregated summary of a PACT project's state, composed from multiple parsed sources."""
    config: PactProjectConfig                # required, Project configuration from pact.yaml.
    phase: PipelinePhase                     # required, Current pipeline phase.
    componentTree: ComponentNodeList         # required, Root-level component tree nodes.
    contracts: PactContractList              # required, All contracts in the project.
    testSuites: PactTestSuiteList            # required, Test results per component.
    totalComponents: int                     # required, Total components in decomposition.
    contractedCount: int                     # required, Number of components with non-missing contracts.
    implementedCount: int                    # required, Number of components with source code.
    testedCount: int                         # required, Number of components with passing tests.

PactProjectSummaryList = list[PactProjectSummary]
# List of project summaries.

class TokenUsage:
    """Token consumption for a single agent session or API call."""
    inputTokens: int                         # required, Number of input/prompt tokens.
    outputTokens: int                        # required, Number of output/completion tokens.
    cacheReadTokens: int                     # required, Tokens read from cache.
    cacheWriteTokens: int                    # required, Tokens written to cache.
    totalTokens: int                         # required, Total tokens (input + output).

class CostRecord:
    """Cost data for a single session or time period."""
    agentId: str                             # required, Agent that incurred the cost.
    sessionId: str                           # required, Session identifier.
    model: str                               # required, Model used for this session.
    tokens: TokenUsage                       # required, Token breakdown.
    costUsd: float                           # required, Estimated cost in USD.
    startedAt: str                           # required, ISO 8601 session start timestamp.
    endedAt: str                             # required, ISO 8601 session end timestamp, or empty if still running.
    projectId: str                           # required, Associated project ID, or empty if not project-scoped.

CostRecordList = list[CostRecord]
# List of cost records.

class CostSummary:
    """Aggregated cost summary over a time range."""
    totalCostUsd: float                      # required, Total cost in USD.
    totalInputTokens: int                    # required, Total input tokens.
    totalOutputTokens: int                   # required, Total output tokens.
    totalTokens: int                         # required, Grand total tokens.
    recordCount: int                         # required, Number of cost records aggregated.
    byAgent: dict                            # required, Map of agentId -> total cost USD.
    byModel: dict                            # required, Map of model -> total cost USD.
    periodStart: str                         # required, ISO 8601 start of aggregation period.
    periodEnd: str                           # required, ISO 8601 end of aggregation period.

class UserTask:
    """A user-created task stored in SQLite (dashboard-specific data)."""
    id: str                                  # required, UUID task identifier.
    title: str                               # required, length(1..500), Task title.
    description: str                         # required, Task description.
    projectId: str                           # required, Associated PACT project ID, or empty.
    assignedAgentId: str                     # required, Assigned agent ID, or empty.
    status: TaskStatus                       # required, Current task status.
    priority: TaskPriority                   # required, Task priority level.
    createdAt: str                           # required, ISO 8601 creation timestamp.
    updatedAt: str                           # required, ISO 8601 last update timestamp.
    completedAt: str                         # required, ISO 8601 completion timestamp, or empty.

class TaskStatus(Enum):
    """Status of a user task."""
    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"
    cancelled = "cancelled"

class TaskPriority(Enum):
    """Priority level for a user task."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

UserTaskList = list[UserTask]
# List of user tasks.

class CreateTaskInput:
    """Input for creating a new task. Validated with Zod."""
    title: str                               # required, length(1..500), Task title.
    description: str = None                  # optional, Task description.
    projectId: str = None                    # optional, Associated project ID.
    assignedAgentId: str = None              # optional, Agent to assign.
    priority: TaskPriority = medium          # optional, Priority level.

class UpdateTaskInput:
    """Input for updating an existing task. All fields optional except id."""
    title: str = None                        # optional, length(1..500), New title.
    description: str = None                  # optional, New description.
    projectId: str = None                    # optional, New project association.
    assignedAgentId: str = None              # optional, New agent assignment.
    status: TaskStatus = None                # optional, New status.
    priority: TaskPriority = None            # optional, New priority.

class UserPreferences:
    """User preferences stored in SQLite."""
    userId: str                              # required, User identifier (default: 'default' for single-user).
    theme: str                               # required, UI theme.
    refreshIntervalMs: int                   # required, range(1000..60000), Dashboard auto-refresh interval in milliseconds.
    openclawBaseDir: str                     # required, Base directory for OpenClaw project.
    pactBaseDir: str                         # required, Base directory for PACT projects.

class CacheEntry:
    """Internal cache entry with TTL tracking."""
    key: str                                 # required, Cache key.
    value: any                               # required, Cached value.
    expiresAt: int                           # required, Unix timestamp in ms when entry expires.
    createdAt: int                           # required, Unix timestamp in ms when entry was created.

class CacheStats:
    """Statistics about the in-memory cache."""
    size: int                                # required, Number of entries in cache.
    hits: int                                # required, Total cache hits since startup.
    misses: int                              # required, Total cache misses since startup.
    evictions: int                           # required, Total evictions since startup.

class ActivityEvent:
    """An activity event for the activity feed, derived from agent sessions and file changes."""
    id: str                                  # required, Unique event identifier.
    type: ActivityEventType                  # required, Type of activity event.
    agentId: str                             # required, Agent that triggered the event, or empty.
    projectId: str                           # required, Related project ID, or empty.
    summary: str                             # required, Human-readable event summary.
    timestamp: str                           # required, ISO 8601 timestamp.
    metadata: dict = None                    # optional, Additional event-specific data.

class ActivityEventType(Enum):
    """Types of activity events."""
    agent_started = "agent_started"
    agent_completed = "agent_completed"
    agent_error = "agent_error"
    contract_created = "contract_created"
    contract_updated = "contract_updated"
    test_run = "test_run"
    file_changed = "file_changed"
    task_created = "task_created"
    task_updated = "task_updated"
    session_started = "session_started"
    session_ended = "session_ended"

ActivityEventList = list[ActivityEvent]
# List of activity events.

class TimeRange:
    """A time range filter for queries."""
    start: str                               # required, ISO 8601 start timestamp.
    end: str                                 # required, ISO 8601 end timestamp.

class PaginationParams:
    """Pagination parameters for list queries."""
    limit: int                               # required, range(1..200), Maximum items to return.
    offset: int                              # required, range(0..100000), Number of items to skip.

class PaginatedResult:
    """A paginated list result with total count."""
    items: list                              # required, The page of items (type varies by endpoint).
    total: int                               # required, Total number of items matching the query.
    limit: int                               # required, Limit used for this page.
    offset: int                              # required, Offset used for this page.
    hasMore: bool                            # required, Whether more items exist beyond this page.

class SafePath:
    """A validated filesystem path guaranteed free of directory traversal. Created only through validatePath."""
    absolute: str                            # required, The resolved absolute path.
    relative: str                            # required, Path relative to the base directory.
    baseDir: str                             # required, The base directory this path was validated against.

class DbMigration:
    """A database migration record."""
    id: int                                  # required, Migration sequence number.
    name: str                                # required, Migration name.
    appliedAt: str                           # required, ISO 8601 timestamp when migration was applied.

DbMigrationList = list[DbMigration]
# List of applied migrations.

def validatePath(
    baseDir: str,
    relativePath: str,
) -> Result:
    """
    Validates and resolves a file path against a base directory, preventing directory traversal attacks. Returns SafePath on success or error if path escapes base directory.

    Preconditions:
      - baseDir must be an absolute path

    Postconditions:
      - On success, SafePath.absolute starts with SafePath.baseDir
      - On success, SafePath.relative contains no '..' segments

    Errors:
      - traversal_detected (DataError): Resolved path is outside baseDir
          kind: permission_denied
      - base_not_absolute (DataError): baseDir is not an absolute path
          kind: malformed

    Side effects: none
    Idempotent: yes
    """
    ...

def readFileRaw(
    filePath: str,
) -> Result:
    """
    Tier 2 internal: Reads a file's contents as a UTF-8 string using try-read-catch-ENOENT. Returns Result<str>. Not part of public facade.

    Preconditions:
      - filePath must be an absolute path

    Postconditions:
      - On success, value is the file contents as a string

    Errors:
      - file_not_found (DataError): File does not exist (ENOENT)
          kind: not_found
      - permission_denied (DataError): Process lacks read permission (EACCES)
          kind: permission_denied
      - io_error (DataError): Any other filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def readDirectoryEntries(
    dirPath: str,
    filterExtension: str = None,
) -> Result:
    """
    Tier 2 internal: Lists entries in a directory. Returns Result<list of str> with entry names (not full paths).

    Preconditions:
      - dirPath must be an absolute path

    Postconditions:
      - On success, value is a list of entry name strings

    Errors:
      - dir_not_found (DataError): Directory does not exist (ENOENT)
          kind: not_found
      - not_a_directory (DataError): Path exists but is not a directory
          kind: malformed
      - permission_denied (DataError): Process lacks read permission
          kind: permission_denied
      - io_error (DataError): Any other filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def parseOpenClawConfig(
    data: any,
    sourceFilePath: str,
    baseDir: str,
) -> Result:
    """
    Tier 2 parser (pure): Parses unknown data as OpenClaw config using Zod .safeParse(). No I/O.

    Postconditions:
      - On success, value is a valid OpenClawConfig
      - On success, all agent workspaceDir paths are resolved to absolute paths

    Errors:
      - malformed_data (DataError): Data does not match OpenClaw config Zod schema
          kind: malformed
      - empty_data (DataError): Data is null, undefined, or empty object
          kind: empty

    Side effects: none
    Idempotent: yes
    """
    ...

def parsePactYaml(
    yamlContent: str,
    sourceFilePath: str,
    baseDir: str,
) -> Result:
    """
    Tier 2 parser (pure): Parses raw YAML string as pact.yaml config using js-yaml safeLoad + Zod. No I/O.

    Postconditions:
      - On success, value is a valid PactProjectConfig

    Errors:
      - invalid_yaml (DataError): YAML syntax error in content
          kind: malformed
      - schema_mismatch (DataError): Parsed YAML does not match pact.yaml Zod schema
          kind: malformed
      - empty_content (DataError): YAML content is empty or whitespace-only
          kind: empty

    Side effects: none
    Idempotent: yes
    """
    ...

def parsePactContract(
    data: any,
    sourceFilePath: str,
) -> Result:
    """
    Tier 2 parser (pure): Parses raw JSON/YAML data as a PACT contract. No I/O.

    Postconditions:
      - On success, value is a valid PactContract

    Errors:
      - malformed_contract (DataError): Data does not match contract Zod schema
          kind: malformed
      - empty_data (DataError): Data is null or empty
          kind: empty

    Side effects: none
    Idempotent: yes
    """
    ...

def parseSessionCostData(
    data: any,
    sourceFilePath: str,
) -> Result:
    """
    Tier 2 parser (pure): Parses raw JSON data from an agent session file to extract token/cost data. No I/O.

    Postconditions:
      - On success, value is a valid CostRecord

    Errors:
      - malformed_session (DataError): Data does not match session Zod schema
          kind: malformed
      - empty_data (DataError): Data is null or empty
          kind: empty
      - missing_cost_fields (DataError): Session data exists but lacks token/cost fields
          kind: malformed

    Side effects: none
    Idempotent: yes
    """
    ...

def parseDecompositionTree(
    fileEntries: dict,
    contractStatuses: dict,
    implementedComponents: list,
    testedComponents: list,
) -> Result:
    """
    Tier 2 parser (pure): Parses decomposition directory structure data into a component tree. Takes a map of file paths to content.

    Postconditions:
      - On success, value is a ComponentNodeList representing the root nodes of the tree
      - Every node's contractStatus matches contractStatuses map or defaults to 'missing'

    Errors:
      - malformed_decomposition (DataError): File contents cannot be parsed as decomposition nodes
          kind: malformed
      - empty_decomposition (DataError): No files provided in fileEntries
          kind: empty

    Side effects: none
    Idempotent: yes
    """
    ...

def derivePipelinePhase(
    hasDecomposition: bool,
    totalComponents: int,
    contractedCount: int,
    implementedCount: int,
    testedCount: int,
) -> PipelinePhase:
    """
    Tier 2 utility (pure): Derives the current pipeline phase from directory existence and content counts.

    Preconditions:
      - All counts are non-negative
      - contractedCount <= totalComponents
      - implementedCount <= totalComponents
      - testedCount <= totalComponents

    Postconditions:
      - Returns 'not_started' if no decomposition and all counts are 0
      - Returns 'complete' if testedCount == totalComponents and totalComponents > 0

    Side effects: none
    Idempotent: yes
    """
    ...

def getOpenClawConfig(
    baseDir: str,
) -> Result:
    """
    Facade: Reads and parses the OpenClaw configuration from openclaw.json at the given base directory. Cached with TTL.

    Preconditions:
      - baseDir must be an absolute path

    Postconditions:
      - On success, value is a valid OpenClawConfig with all paths resolved

    Errors:
      - config_not_found (DataError): openclaw.json does not exist at baseDir
          kind: not_found
      - config_malformed (DataError): openclaw.json exists but fails Zod validation
          kind: malformed
      - config_empty (DataError): openclaw.json exists but is empty
          kind: empty
      - permission_denied (DataError): Cannot read openclaw.json due to permissions
          kind: permission_denied
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getAgent(
    baseDir: str,
    agentId: str,
) -> Result:
    """
    Facade: Gets a single agent definition by ID from the OpenClaw config.

    Preconditions:
      - baseDir must be an absolute path
      - agentId must be non-empty

    Postconditions:
      - On success, value is a valid AgentDefinition

    Errors:
      - agent_not_found (DataError): No agent with given ID exists in config
          kind: not_found
      - config_not_found (DataError): openclaw.json does not exist
          kind: not_found
      - config_malformed (DataError): openclaw.json fails validation
          kind: malformed

    Side effects: none
    Idempotent: yes
    """
    ...

def listAgents(
    baseDir: str,
) -> Result:
    """
    Facade: Lists all agent definitions from the OpenClaw config.

    Preconditions:
      - baseDir must be an absolute path

    Postconditions:
      - On success, value is an AgentList (may be empty if config has no agents)

    Errors:
      - config_not_found (DataError): openclaw.json does not exist
          kind: not_found
      - config_malformed (DataError): openclaw.json fails validation
          kind: malformed
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getProject(
    projectDir: str,
) -> Result:
    """
    Facade: Reads and assembles a full PACT project summary from a project directory. Composes parsers for pact.yaml, decomposition/, contracts/, tests/, and src/.

    Preconditions:
      - projectDir must be an absolute path

    Postconditions:
      - On success, value is a complete PactProjectSummary
      - totalComponents, contractedCount, implementedCount, testedCount are consistent with componentTree

    Errors:
      - project_not_found (DataError): pact.yaml does not exist at projectDir
          kind: not_found
      - project_malformed (DataError): pact.yaml exists but fails validation
          kind: malformed
      - project_empty (DataError): pact.yaml is empty
          kind: empty
      - permission_denied (DataError): Cannot read project directory or files
          kind: permission_denied
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def listProjects(
    baseDir: str,
) -> Result:
    """
    Facade: Discovers and summarizes all PACT projects under a base directory. Each subdirectory containing pact.yaml is treated as a project.

    Preconditions:
      - baseDir must be an absolute path

    Postconditions:
      - On success, value is a PactProjectSummaryList
      - Projects with malformed pact.yaml are excluded from the list (logged, not thrown)

    Errors:
      - base_not_found (DataError): Base directory does not exist
          kind: not_found
      - permission_denied (DataError): Cannot read base directory
          kind: permission_denied
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getProjectPipelineStatus(
    projectDir: str,
) -> Result:
    """
    Facade: Returns just the pipeline phase and high-level counts for a project. Lighter weight than full getProject.

    Preconditions:
      - projectDir must be an absolute path

    Postconditions:
      - On success, value contains phase, totalComponents, contractedCount, implementedCount, testedCount

    Errors:
      - project_not_found (DataError): pact.yaml does not exist
          kind: not_found
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getProjectContracts(
    projectDir: str,
) -> Result:
    """
    Facade: Lists all PACT contracts in a project's contracts/ directory.

    Preconditions:
      - projectDir must be an absolute path

    Postconditions:
      - On success, value is a PactContractList

    Errors:
      - contracts_dir_not_found (DataError): contracts/ directory does not exist
          kind: not_found
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getProjectTestResults(
    projectDir: str,
) -> Result:
    """
    Facade: Aggregates test results for all components in a project.

    Preconditions:
      - projectDir must be an absolute path

    Postconditions:
      - On success, value is a PactTestSuiteList

    Errors:
      - tests_dir_not_found (DataError): tests/ directory does not exist
          kind: not_found
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getProjectComponentTree(
    projectDir: str,
) -> Result:
    """
    Facade: Returns the component decomposition tree for a project.

    Preconditions:
      - projectDir must be an absolute path

    Postconditions:
      - On success, value is a ComponentNodeList of root-level nodes

    Errors:
      - decomposition_not_found (DataError): decomposition/ directory does not exist
          kind: not_found
      - malformed_decomposition (DataError): Decomposition files cannot be parsed
          kind: malformed
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getCostRecords(
    baseDir: str,
    timeRange: TimeRange = None,
    agentId: str = None,
    projectId: str = None,
) -> Result:
    """
    Facade: Reads token/cost data from agent session files for a given time range.

    Preconditions:
      - baseDir must be an absolute path

    Postconditions:
      - On success, value is a CostRecordList sorted by startedAt descending
      - All records fall within timeRange if provided

    Errors:
      - config_not_found (DataError): openclaw.json not found (needed to discover agent workspaces)
          kind: not_found
      - no_sessions (DataError): No session files found matching criteria
          kind: empty
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getCostSummary(
    baseDir: str,
    timeRange: TimeRange,
) -> Result:
    """
    Facade: Aggregates cost records into a summary over a time range.

    Preconditions:
      - baseDir must be an absolute path
      - timeRange.start must be before timeRange.end

    Postconditions:
      - On success, value is a valid CostSummary
      - totalCostUsd equals sum of all individual record costs
      - byAgent keys are a subset of known agent IDs

    Errors:
      - config_not_found (DataError): openclaw.json not found
          kind: not_found
      - no_data (DataError): No cost records found in time range
          kind: empty
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getActivityFeed(
    baseDir: str,
    pagination: PaginationParams = None,
    agentId: str = None,
    projectId: str = None,
    eventTypes: list = None,
) -> Result:
    """
    Facade: Returns recent activity events from agent sessions and file changes, ordered by timestamp descending.

    Preconditions:
      - baseDir must be an absolute path

    Postconditions:
      - On success, value is a PaginatedResult with items of type ActivityEventList
      - Events are sorted by timestamp descending

    Errors:
      - config_not_found (DataError): openclaw.json not found
          kind: not_found
      - io_error (DataError): Unexpected filesystem error
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def initDatabase(
    dbPath: str,
) -> Result:
    """
    SQLite: Initializes the SQLite database, runs migrations, and enables WAL mode. Must be called once at application startup.

    Postconditions:
      - On success, database is ready for queries
      - WAL mode is enabled (unless :memory:)
      - All migration files have been applied in order
      - migrations table exists and records applied migrations

    Errors:
      - db_create_failed (DataError): Cannot create or open database file
          kind: io_error
      - migration_failed (DataError): A migration SQL statement failed
          kind: malformed
      - permission_denied (DataError): Cannot write to database path
          kind: permission_denied

    Side effects: none
    Idempotent: yes
    """
    ...

def closeDatabase() -> Result:
    """
    SQLite: Closes the database connection gracefully.

    Preconditions:
      - Database must have been initialized via initDatabase

    Postconditions:
      - Database connection is closed
      - No further queries can be made until re-initialized

    Errors:
      - not_initialized (DataError): Database was never initialized
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getAppliedMigrations() -> Result:
    """
    SQLite: Returns list of applied database migrations.

    Preconditions:
      - Database must be initialized

    Postconditions:
      - On success, value is a DbMigrationList ordered by id ascending

    Errors:
      - not_initialized (DataError): Database was never initialized
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def createTask(
    input: CreateTaskInput,
) -> Result:
    """
    SQLite Facade: Creates a new user task in SQLite.

    Preconditions:
      - Database must be initialized
      - input must pass Zod validation

    Postconditions:
      - On success, value is the created UserTask with generated id, createdAt, updatedAt
      - Task status defaults to 'todo'
      - id is a UUID v4

    Errors:
      - validation_failed (DataError): Input fails Zod schema validation
          kind: malformed
      - db_error (DataError): SQLite insert fails
          kind: io_error

    Side effects: none
    Idempotent: no
    """
    ...

def getTask(
    taskId: str,
) -> Result:
    """
    SQLite Facade: Retrieves a single task by ID.

    Preconditions:
      - Database must be initialized
      - taskId must be non-empty

    Postconditions:
      - On success, value is a valid UserTask

    Errors:
      - task_not_found (DataError): No task with given ID exists
          kind: not_found
      - db_error (DataError): SQLite query fails
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def listTasks(
    pagination: PaginationParams = None,
    projectId: str = None,
    assignedAgentId: str = None,
    status: str = None,
    priority: str = None,
) -> Result:
    """
    SQLite Facade: Lists tasks with optional filters and pagination.

    Preconditions:
      - Database must be initialized

    Postconditions:
      - On success, value is a PaginatedResult with items of type UserTaskList
      - Results are ordered by createdAt descending

    Errors:
      - db_error (DataError): SQLite query fails
          kind: io_error
      - invalid_filter (DataError): status or priority filter is not a valid enum value
          kind: malformed

    Side effects: none
    Idempotent: yes
    """
    ...

def updateTask(
    taskId: str,
    input: UpdateTaskInput,
) -> Result:
    """
    SQLite Facade: Updates an existing task. Only provided fields are updated.

    Preconditions:
      - Database must be initialized
      - taskId must be non-empty

    Postconditions:
      - On success, value is the updated UserTask
      - updatedAt is set to current timestamp
      - If status changes to 'done', completedAt is set to current timestamp
      - If status changes from 'done' to another status, completedAt is cleared

    Errors:
      - task_not_found (DataError): No task with given ID exists
          kind: not_found
      - validation_failed (DataError): Input fails Zod schema validation
          kind: malformed
      - db_error (DataError): SQLite update fails
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def deleteTask(
    taskId: str,
) -> Result:
    """
    SQLite Facade: Deletes a task by ID.

    Preconditions:
      - Database must be initialized
      - taskId must be non-empty

    Postconditions:
      - On success, value is the deleted UserTask (returned before deletion)
      - Task no longer exists in database

    Errors:
      - task_not_found (DataError): No task with given ID exists
          kind: not_found
      - db_error (DataError): SQLite delete fails
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def getUserPreferences(
    userId: str = default,
) -> Result:
    """
    SQLite Facade: Gets user preferences, creating default if not exists.

    Preconditions:
      - Database must be initialized

    Postconditions:
      - On success, value is a valid UserPreferences
      - If no preferences exist, returns defaults and persists them

    Errors:
      - db_error (DataError): SQLite query/insert fails
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def updateUserPreferences(
    userId: str,
    updates: dict,
) -> Result:
    """
    SQLite Facade: Updates user preferences. Merges with existing preferences.

    Preconditions:
      - Database must be initialized
      - userId must be non-empty

    Postconditions:
      - On success, value is the complete updated UserPreferences

    Errors:
      - validation_failed (DataError): Updates contain invalid field values
          kind: malformed
      - db_error (DataError): SQLite update fails
          kind: io_error

    Side effects: none
    Idempotent: yes
    """
    ...

def invalidateCache(
    key: str = None,
    prefix: str = None,
) -> int:
    """
    Cache: Invalidates cache entries. Can target specific keys, key prefixes, or clear all.

    Postconditions:
      - Returns count of entries invalidated
      - Invalidated entries are immediately removed from cache

    Side effects: none
    Idempotent: yes
    """
    ...

def getCacheStats() -> CacheStats:
    """
    Cache: Returns current cache statistics.

    Postconditions:
      - All counts are non-negative

    Side effects: none
    Idempotent: yes
    """
    ...

# ── REQUIRED EXPORTS ──────────────────────────────────
# Your implementation module MUST export ALL of these names
# with EXACTLY these spellings. Tests import them by name.
# __all__ = ['ErrorKind', 'DataError', 'ResultOk', 'ResultErr', 'Result', 'AgentRole', 'AgentStatus', 'AgentDefinition', 'AgentList', 'OpenClawConfig', 'PipelinePhase', 'ContractStatus', 'PactContract', 'PactContractList', 'TestResult', 'PactTestSuite', 'PactTestSuiteList', 'ComponentNode', 'ComponentNodeList', 'PactProjectConfig', 'PactProjectSummary', 'PactProjectSummaryList', 'TokenUsage', 'CostRecord', 'CostRecordList', 'CostSummary', 'UserTask', 'TaskStatus', 'TaskPriority', 'UserTaskList', 'CreateTaskInput', 'UpdateTaskInput', 'UserPreferences', 'CacheEntry', 'CacheStats', 'ActivityEvent', 'ActivityEventType', 'ActivityEventList', 'TimeRange', 'PaginationParams', 'PaginatedResult', 'SafePath', 'DbMigration', 'DbMigrationList', 'validatePath', 'readFileRaw', 'readDirectoryEntries', 'parseOpenClawConfig', 'parsePactYaml', 'parsePactContract', 'parseSessionCostData', 'parseDecompositionTree', 'derivePipelinePhase', 'getOpenClawConfig', 'getAgent', 'listAgents', 'getProject', 'listProjects', 'getProjectPipelineStatus', 'getProjectContracts', 'getProjectTestResults', 'getProjectComponentTree', 'getCostRecords', 'getCostSummary', 'getActivityFeed', 'initDatabase', 'closeDatabase', 'getAppliedMigrations', 'createTask', 'getTask', 'listTasks', 'updateTask', 'deleteTask', 'getUserPreferences', 'updateUserPreferences', 'invalidateCache', 'getCacheStats']
