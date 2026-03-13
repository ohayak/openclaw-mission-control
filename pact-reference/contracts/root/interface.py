# === Root (root) v1 ===
#  Dependencies: activity_cost_pages, agent_dashboard, data_layer, e2e_tests, foundation, pact_visualization, project_task_management, sse_event_system
# Contract specifications for cross-cutting concerns in OpenClaw Mission Control. Defines pure TypeScript type definitions and protocols (Result, serialization, events, aggregations, errors, naming conventions) that subsystems must conform to. Zero runtime code—purely types and interfaces. No dependencies; all subsystems reference root for conformance contracts.

# Module invariants:
#   - All Result values have exactly one of ok=true with value OR ok=false with error (never both, never neither)
#   - All StandardError.timestamp values are valid ISO 8601 strings with timezone
#   - All EventEnvelope.id values are globally unique (enforced by nanoid/uuid collision resistance)
#   - All EventEnvelope.version values equal 'v1' for current schema
#   - All EventEnvelope.type values match /^[a-z]+([.][a-z_]+)+$/ (dot-notation lowercase)
#   - All ISODateString.value fields match /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/
#   - All FilesystemError.code values are valid FilesystemErrorCode enum variants
#   - All AggregateQuery.period_end values are >= period_start (chronological ordering)
#   - All Serializable implementers must produce JSON-serializable output (no circular refs, Functions, Symbols)
#   - All Deserializable implementers must validate via Zod before constructing instances
#   - All subsystems return Result<T, StandardError> for fallible operations (never throw exceptions for expected errors)
#   - All event payloads are JSON-serializable (validated in createEventEnvelope)
#   - All naming convention rules are documented in JSDoc and enforced via validateNamingConvention
#   - Root has zero dependencies (purely type definitions and protocols)
#   - Root exports no runtime code (only TypeScript types and type guards)

class ErrorKind(Enum):
    """Standard error categories for all subsystems. Finite set of error types for discriminated error handling."""
    NotFound = "NotFound"
    ValidationError = "ValidationError"
    ConflictError = "ConflictError"
    DatabaseError = "DatabaseError"
    FilesystemError = "FilesystemError"
    ParseError = "ParseError"
    NetworkError = "NetworkError"
    PermissionDenied = "PermissionDenied"
    Timeout = "Timeout"
    UnknownError = "UnknownError"

class StandardError:
    """Standard error interface that all subsystems implement. Enables uniform error handling and reporting across the application."""
    kind: ErrorKind                          # required, Error category discriminant
    message: str                             # required, length(1..10000), Human-readable error message
    context: dict = {}                       # optional, Additional structured error context (field names, paths, codes, etc.)
    cause: str = None                        # optional, Underlying error message or stack trace from source system
    timestamp: str                           # required, regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$), ISO 8601 timestamp when error occurred

class ResultOk:
    """Success variant of Result discriminated union"""
    ok: bool                                 # required, custom(value === true), Literal true for success variant
    value: any                               # required, The success payload. Actual type depends on function signature (generic T).

class ResultErr:
    """Error variant of Result discriminated union"""
    ok: bool                                 # required, custom(value === false), Literal false for error variant
    error: StandardError                     # required, The structured error value

Result = ResultOk | ResultErr

class ISODateString:
    """ISO 8601 timestamp string type. All date/time values must use this format (no Date objects across serialization boundaries)."""
    value: str                               # required, regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$), ISO 8601 formatted timestamp with timezone (YYYY-MM-DDTHH:mm:ss.sssZ or +HH:mm)

class Serializable:
    """Protocol contract for types that can be serialized to JSON/NDJSON. All SSE event payloads and API responses must implement this contract."""
    toJSON: str                              # required, Signature of toJSON method: () => Record<string, JSONValue>. Implementers must provide this method that returns a JSON-serializable object with no circular references, Functions, or Symbols.

class Deserializable:
    """Protocol contract for types that can be deserialized from JSON. All persisted events and API request bodies must implement this contract."""
    fromJSON: str                            # required, Signature of static fromJSON method: (data: Record<string, JSONValue>) => Result<T, StandardError>. Implementers must validate via Zod before constructing instance.

class EventVersion(Enum):
    """Event schema version discriminator for forward compatibility"""
    v1 = "v1"

class EventEnvelope:
    """Standard envelope for all SSE and persisted events. Subsystems must wrap event payloads in this envelope. Enables versioning, ordering, and deduplication."""
    id: str                                  # required, regex(^[a-zA-Z0-9_-]{21,}$|^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$), Unique event identifier (UUID v4 or nanoid). Used for SSE Last-Event-ID and deduplication.
    type: str                                # required, regex(^[a-z]+([.][a-z_]+)+$), Dot-notation event type (e.g., 'agent.started', 'pact.transition'). Used for filtering and routing.
    timestamp: str                           # required, regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$), ISO 8601 timestamp when event occurred
    version: EventVersion                    # required, Event schema version (always v1 for current schema)
    payload: dict                            # required, Event-specific data conforming to event type schema. Must be JSON-serializable.
    metadata: dict = {}                      # optional, Optional envelope-level metadata (trace IDs, correlation IDs, source system)

class TimeBucketGranularity(Enum):
    """Time bucket granularities for aggregation queries"""
    minute = "minute"
    hour = "hour"
    day = "day"
    week = "week"
    month = "month"

class AggregationDimension(Enum):
    """Standard dimensions for grouping aggregations (cost, metrics, activity)"""
    agent_id = "agent_id"
    project_id = "project_id"
    model = "model"
    time_bucket = "time_bucket"
    status = "status"
    priority = "priority"
    event_type = "event_type"

class AggregateQuery:
    """Protocol contract for aggregate query parameters. Subsystems use this for cost/metrics/activity aggregation queries."""
    dimensions: list                         # required, List of AggregationDimension values to group by
    time_bucket: TimeBucketGranularity = None # optional, Time bucket size when 'time_bucket' is in dimensions
    period_start: str                        # required, regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$), ISO 8601 start of query period
    period_end: str                          # required, regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$), ISO 8601 end of query period
    filters: dict = {}                       # optional, Optional dimension filters (e.g., {agent_id: 'agent-1', project_id: 'proj-2'})

class FilesystemErrorCode(Enum):
    """Standard filesystem error codes mapped from Node.js ENOENT, EACCES, etc. Used by data layer for filesystem error handling."""
    ENOENT = "ENOENT"
    EACCES = "EACCES"
    EISDIR = "EISDIR"
    ENOTDIR = "ENOTDIR"
    EMFILE = "EMFILE"
    ENOSPC = "ENOSPC"
    EPERM = "EPERM"
    EEXIST = "EEXIST"
    EINVAL = "EINVAL"
    EIO = "EIO"
    UNKNOWN = "UNKNOWN"

class FilesystemError:
    """Structured filesystem error with path context. Data layer maps Node.js fs errors to this type."""
    code: FilesystemErrorCode                # required, Filesystem error code
    path: str                                # required, File or directory path that caused the error
    operation: str                           # required, Filesystem operation that failed (read, write, readdir, stat, etc.)
    message: str                             # required, Human-readable error message
    syscall: str = None                      # optional, System call that failed (open, read, stat, etc.)

class FixtureData:
    """Generic wrapper for test fixture data. Testing subsystem uses this to type fixture objects."""
    data: any                                # required, The fixture data payload. Actual type depends on fixture type (generic T).
    metadata: dict                           # required, Fixture metadata (description, version, created_at, tags)

class NamingConventionRule(Enum):
    """Naming convention rules enforced across the codebase. Documented in JSDoc, validated in linting."""
    FUNCTION_NAMES_CAMEL_CASE = "FUNCTION_NAMES_CAMEL_CASE"
    TYPE_NAMES_PASCAL_CASE = "TYPE_NAMES_PASCAL_CASE"
    ENUM_VARIANTS_SNAKE_CASE = "ENUM_VARIANTS_SNAKE_CASE"
    COMPONENT_IDS_SNAKE_CASE = "COMPONENT_IDS_SNAKE_CASE"
    EVENT_TYPES_DOT_NOTATION_LOWERCASE = "EVENT_TYPES_DOT_NOTATION_LOWERCASE"
    API_ROUTES_KEBAB_CASE = "API_ROUTES_KEBAB_CASE"
    DATABASE_COLUMNS_SNAKE_CASE = "DATABASE_COLUMNS_SNAKE_CASE"
    BRANDED_TYPES_SUFFIX_ID = "BRANDED_TYPES_SUFFIX_ID"

def createResultOk(
    value: any,
) -> ResultOk:
    """
    Pure factory function to construct a ResultOk value. Used by subsystems to create success results. No validation—caller must ensure value is valid.

    Postconditions:
      - Returned result has ok=true
      - Returned result.value === input value

    Side effects: none
    Idempotent: yes
    """
    ...

def createResultErr(
    error: StandardError,
) -> ResultErr:
    """
    Pure factory function to construct a ResultErr value. Used by subsystems to create error results. Validates that error conforms to StandardError shape via runtime check.

    Preconditions:
      - error.kind must be valid ErrorKind variant
      - error.message must be non-empty
      - error.timestamp must be valid ISO 8601

    Postconditions:
      - Returned result has ok=false
      - Returned result.error === input error

    Errors:
      - InvalidErrorStructure (ValidationError): error does not conform to StandardError shape
          message: Error must conform to StandardError interface

    Side effects: none
    Idempotent: yes
    """
    ...

def isResultOk(
    result: Result,
) -> bool:
    """
    Pure type guard to check if Result is the Ok variant. Used for discriminated union narrowing in subsystems.

    Postconditions:
      - Returns true if result.ok === true
      - Returns false if result.ok === false

    Side effects: none
    Idempotent: yes
    """
    ...

def isResultErr(
    result: Result,
) -> bool:
    """
    Pure type guard to check if Result is the Err variant. Used for discriminated union narrowing in subsystems.

    Postconditions:
      - Returns true if result.ok === false
      - Returns false if result.ok === true

    Side effects: none
    Idempotent: yes
    """
    ...

def toISODateString(
    input: any,
) -> str:
    """
    Pure converter from Date object or timestamp number to ISO 8601 string. Used by subsystems to ensure all date/time values are serialized consistently. No Date objects across serialization boundaries.

    Preconditions:
      - If input is number, must be valid Unix timestamp in milliseconds
      - If input is Date, must be valid Date object (not Invalid Date)
      - If input is string, must be parseable as ISO 8601

    Postconditions:
      - Returned string matches ISO 8601 regex ^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$
      - Timezone is always included (Z or +HH:mm)

    Errors:
      - InvalidDateInput (ValidationError): Input is not a Date, number, or parseable ISO string
          message: Input must be Date, Unix timestamp, or ISO 8601 string
      - InvalidDate (ValidationError): Input Date object is Invalid Date
          message: Date object is invalid

    Side effects: none
    Idempotent: yes
    """
    ...

def fromISODateString(
    isoString: str,            # regex(^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$)
) -> Result:
    """
    Pure parser from ISO 8601 string to Date object. Used when subsystems need to perform date arithmetic (not for serialization). Returns Result<Date, StandardError>.

    Preconditions:
      - isoString matches ISO 8601 regex

    Postconditions:
      - On success, result.value is valid Date object with time matching isoString
      - On error, result.error.kind === 'ParseError'

    Errors:
      - ParseError (ParseError): isoString cannot be parsed into valid Date (malformed, out-of-range values)
          message: Failed to parse ISO 8601 string into Date

    Side effects: none
    Idempotent: yes
    """
    ...

def createEventEnvelope(
    type: str,                 # regex(^[a-z]+([.][a-z_]+)+$)
    payload: dict,
    metadata: dict = {},
) -> EventEnvelope:
    """
    Pure factory to construct an EventEnvelope from event type, payload, and optional metadata. Generates unique ID (nanoid) and current timestamp. Used by subsystems when emitting events to SSE bus.

    Preconditions:
      - payload must be JSON-serializable (no circular refs, Functions, Symbols)

    Postconditions:
      - Returned envelope has unique id (nanoid)
      - Returned envelope.timestamp is current time as ISO 8601 string
      - Returned envelope.version === 'v1'
      - Returned envelope.type === input type
      - Returned envelope.payload === input payload
      - Returned envelope.metadata === input metadata

    Errors:
      - InvalidEventType (ValidationError): type does not match dot-notation regex
          message: Event type must be dot-notation lowercase
      - NonSerializablePayload (ValidationError): payload contains non-serializable values (circular refs, Functions, Symbols)
          message: Event payload must be JSON-serializable

    Side effects: none
    Idempotent: no
    """
    ...

def mapNodeFsError(
    nodeError: any,
    operation: str,
) -> FilesystemError:
    """
    Pure mapper from Node.js fs error to FilesystemError. Used by data layer to convert Node.js errors to structured domain errors. Extracts code, path, syscall from Node error object.

    Postconditions:
      - Returned error.code is mapped from nodeError.code to FilesystemErrorCode enum (defaults to UNKNOWN if unrecognized)
      - Returned error.path is nodeError.path if present, otherwise empty string
      - Returned error.operation === input operation
      - Returned error.syscall is nodeError.syscall if present

    Side effects: none
    Idempotent: yes
    """
    ...

def createStandardError(
    kind: ErrorKind,
    message: str,              # length(1..10000)
    context: dict = {},
    cause: str = None,
) -> StandardError:
    """
    Pure factory to construct a StandardError from kind, message, and optional context/cause. Automatically sets timestamp to current time as ISO 8601 string. Used by all subsystems to create uniform errors.

    Preconditions:
      - message length between 1 and 10000 characters

    Postconditions:
      - Returned error.kind === input kind
      - Returned error.message === input message
      - Returned error.context === input context (or {} if omitted)
      - Returned error.cause === input cause (or empty string if omitted)
      - Returned error.timestamp is current time as ISO 8601 string

    Errors:
      - InvalidMessage (ValidationError): message is empty or exceeds 10000 characters
          message: Error message must be 1-10000 characters

    Side effects: none
    Idempotent: no
    """
    ...

def validateNamingConvention(
    name: str,
    rule: NamingConventionRule,
) -> Result:
    """
    Pure validator to check if a name adheres to a NamingConventionRule. Used by linting tools and code generation utilities. Returns Result<bool, StandardError> where value=true means valid, error variant means invalid with details.

    Preconditions:
      - name is non-empty
      - rule is valid NamingConventionRule variant

    Postconditions:
      - On success, result.value === true if name matches rule pattern
      - On error, result.error.kind === 'ValidationError' with message explaining violation

    Errors:
      - InvalidFunctionName (ValidationError): rule is FUNCTION_NAMES_CAMEL_CASE and name does not match /^[a-z][a-zA-Z0-9]*$/
          message: Function names must be camelCase
      - InvalidTypeName (ValidationError): rule is TYPE_NAMES_PASCAL_CASE and name does not match /^[A-Z][a-zA-Z0-9]*$/
          message: Type names must be PascalCase
      - InvalidEnumVariant (ValidationError): rule is ENUM_VARIANTS_SNAKE_CASE and name does not match /^[a-z][a-z0-9_]*$/
          message: Enum variants must be snake_case
      - InvalidComponentId (ValidationError): rule is COMPONENT_IDS_SNAKE_CASE and name does not match /^[a-z][a-z0-9_]*$/
          message: Component IDs must be snake_case
      - InvalidEventType (ValidationError): rule is EVENT_TYPES_DOT_NOTATION_LOWERCASE and name does not match /^[a-z]+([.][a-z_]+)+$/
          message: Event types must be dot.notation.lowercase
      - InvalidApiRoute (ValidationError): rule is API_ROUTES_KEBAB_CASE and name does not match /^[a-z][a-z0-9-]*$/
          message: API routes must be kebab-case
      - InvalidDatabaseColumn (ValidationError): rule is DATABASE_COLUMNS_SNAKE_CASE and name does not match /^[a-z][a-z0-9_]*$/
          message: Database columns must be snake_case
      - InvalidBrandedType (ValidationError): rule is BRANDED_TYPES_SUFFIX_ID and name does not match /[A-Z][a-zA-Z0-9]*Id$/
          message: Branded ID types must be PascalCase ending with 'Id'

    Side effects: none
    Idempotent: yes
    """
    ...

# ── REQUIRED EXPORTS ──────────────────────────────────
# Your implementation module MUST export ALL of these names
# with EXACTLY these spellings. Tests import them by name.
# __all__ = ['ErrorKind', 'StandardError', 'ResultOk', 'ResultErr', 'Result', 'ISODateString', 'Serializable', 'Deserializable', 'EventVersion', 'EventEnvelope', 'TimeBucketGranularity', 'AggregationDimension', 'AggregateQuery', 'FilesystemErrorCode', 'FilesystemError', 'FixtureData', 'NamingConventionRule', 'createResultOk', 'createResultErr', 'ValidationError', 'isResultOk', 'isResultErr', 'toISODateString', 'fromISODateString', 'ParseError', 'createEventEnvelope', 'mapNodeFsError', 'createStandardError', 'validateNamingConvention']
