# === Foundation & Infrastructure (foundation) v1 ===
# Next.js 15 project scaffolding, TypeScript strict config, Tailwind v4 + shadcn/ui setup, SQLite schema with auto-migration on startup (better-sqlite3 with WAL mode, externalized in next.config.js), simple password auth with secure cookie middleware, the lib/db/ module with typed query wrappers, shared TypeScript types in lib/types/, Zod schemas for all external inputs, app layout with dark-mode-by-default theme, responsive shell with sidebar navigation, and error boundaries at page level. Includes the login page/flow and auth middleware that gates all routes.

# Module invariants:
#   - All database connections use WAL mode
#   - All database tables use STRICT mode
#   - Migrations are applied exactly once per version
#   - Session cookies are HttpOnly and Secure in production
#   - All API responses use ApiError shape for errors
#   - No Date objects in API responses (all dates are ISO 8601 strings)
#   - tsconfig strict mode is enabled with noUncheckedIndexedAccess
#   - All external inputs are validated with Zod before use
#   - All data access functions return Result<T, DomainError>
#   - Database queries wrap raw results with Zod validation

class Database:
    """better-sqlite3 database connection handle with WAL mode enabled"""
    handle: any                              # required, Opaque better-sqlite3 Database instance
    isOpen: bool                             # required, Connection status flag

class MigrationResult:
    """Result of migration execution"""
    appliedCount: int                        # required, Number of migrations applied in this run
    currentVersion: int                      # required, Final database version after migrations
    migrationsRun: list                      # required, List of migration file names applied

class ProjectId:
    """Branded string type for project identifiers"""
    _brand: str                              # required, Literal 'ProjectId' for type branding
    value: str                               # required, Underlying string value

class TaskId:
    """Branded string type for task identifiers"""
    _brand: str                              # required, Literal 'TaskId' for type branding
    value: str                               # required, Underlying string value

class UserId:
    """Branded string type for user identifiers"""
    _brand: str                              # required, Literal 'UserId' for type branding
    value: str                               # required, Underlying string value

class Result:
    """Generic Result type for error handling in data layer"""
    success: bool                            # required, True if operation succeeded, false otherwise
    value: any = None                        # optional, Success value (present when success=true)
    error: DomainError = None                # optional, Error value (present when success=false)

class DomainError:
    """Typed domain-level error"""
    code: ErrorCode                          # required, Error classification code
    message: str                             # required, Human-readable error description
    cause: str = None                        # optional, Underlying error message or context

class ErrorCode(Enum):
    """Domain error classification"""
    NotFound = "NotFound"
    AlreadyExists = "AlreadyExists"
    InvalidInput = "InvalidInput"
    DatabaseError = "DatabaseError"
    MigrationError = "MigrationError"
    AuthError = "AuthError"
    Unknown = "Unknown"

class SessionData:
    """User session object stored in encrypted cookie"""
    userId: str                              # required, Authenticated user ID
    expiresAt: int                           # required, Unix timestamp (ms) when session expires
    createdAt: int                           # required, Unix timestamp (ms) when session was created

class LoginRequest:
    """API request body for login"""
    username: str                            # required, length(1..256), User username
    password: str                            # required, length(1..1024), User password (plaintext in transit, TLS required)

class LoginResponse:
    """API response for successful login"""
    success: bool                            # required, Always true for successful login
    userId: str                              # required, Authenticated user ID
    expiresAt: str                           # required, ISO 8601 timestamp when session expires

class LogoutResponse:
    """API response for logout"""
    success: bool                            # required, Always true for successful logout

class ApiError:
    """Normalized API error response shape"""
    error: str                               # required, Error code or short identifier
    message: str                             # required, Human-readable error message
    status: int                              # required, HTTP status code

class User:
    """User database record (from Zod schema)"""
    id: str                                  # required, Primary key UUID
    username: str                            # required, Unique username
    passwordHash: str                        # required, bcrypt hash of password
    createdAt: str                           # required, ISO 8601 creation timestamp

class Task:
    """Task database record (from Zod schema)"""
    id: str                                  # required, Primary key UUID
    projectId: str                           # required, Foreign key to projects table
    title: str                               # required, Task title
    description: str = None                  # optional, Task description or body
    status: str                              # required, Task status (enum: todo, in_progress, done)
    createdAt: str                           # required, ISO 8601 creation timestamp
    updatedAt: str                           # required, ISO 8601 last update timestamp

class Project:
    """Project database record (from Zod schema)"""
    id: str                                  # required, Primary key UUID
    name: str                                # required, Project name
    description: str = None                  # optional, Project description
    createdAt: str                           # required, ISO 8601 creation timestamp
    updatedAt: str                           # required, ISO 8601 last update timestamp

class MigrationRecord:
    """Database migration metadata record"""
    version: int                             # required, Migration version number
    name: str                                # required, Migration file name
    appliedAt: str                           # required, ISO 8601 timestamp when migration was applied

class ErrorBoundaryProps:
    """Props passed to error.tsx boundary component"""
    error: any                               # required, Error object (Error instance or unknown)
    reset: any                               # required, Function to reset error boundary state

class MiddlewareConfig:
    """Next.js middleware configuration export"""
    matcher: list                            # required, Array of path patterns to apply middleware

class NextRequest:
    """Next.js request object (opaque)"""
    url: str                                 # required, Request URL
    cookies: any                             # required, Cookie store API

class NextResponse:
    """Next.js response object (opaque)"""
    status: int                              # required, HTTP status code
    headers: any                             # required, Response headers

def initDatabase(
    dbPath: str,
) -> Database:
    """
    Initialize better-sqlite3 database connection with WAL mode. Creates database file if it does not exist. Sets PRAGMA journal_mode=WAL and foreign_keys=ON.

    Preconditions:
      - dbPath is a valid filesystem path or ':memory:'

    Postconditions:
      - Database connection is open
      - WAL mode is enabled
      - Foreign keys are enabled

    Errors:
      - DatabaseOpenError (DatabaseError): Cannot open or create database file at dbPath
      - PragmaSetError (DatabaseError): Cannot set WAL mode or foreign_keys pragma

    Side effects: none
    Idempotent: no
    """
    ...

def runMigrations(
    db: Database,
) -> Result:
    """
    Apply all pending migrations from lib/db/migrations/ directory. Uses BEGIN IMMEDIATE transaction to prevent concurrent execution. Migrations are numbered SQL files (001_initial.sql, 002_add_column.sql, etc.). Tracks applied migrations in internal 'migrations' table.

    Preconditions:
      - db.isOpen is true
      - lib/db/migrations/ directory exists

    Postconditions:
      - All pending migrations are applied
      - migrations table is updated
      - Database version is current

    Errors:
      - MigrationDirectoryNotFound (MigrationError): lib/db/migrations/ directory does not exist
      - MigrationFileMalformed (MigrationError): Migration file contains invalid SQL
      - ConcurrentMigrationAttempt (MigrationError): Another process is running migrations (transaction lock conflict)
      - DatabaseWriteError (DatabaseError): Cannot write to migrations table or execute migration SQL

    Side effects: none
    Idempotent: no
    """
    ...

def closeDatabase(
    db: Database,
) -> None:
    """
    Close database connection and release resources. Safe to call multiple times (idempotent).

    Postconditions:
      - db.isOpen is false
      - Database connection is released

    Side effects: none
    Idempotent: yes
    """
    ...

def asProjectId(
    value: str,
) -> ProjectId:
    """
    Brand a string as a ProjectId. Does not validate format, only applies type branding.

    Postconditions:
      - Return value has _brand='ProjectId'

    Side effects: none
    Idempotent: no
    """
    ...

def asTaskId(
    value: str,
) -> TaskId:
    """
    Brand a string as a TaskId. Does not validate format, only applies type branding.

    Postconditions:
      - Return value has _brand='TaskId'

    Side effects: none
    Idempotent: no
    """
    ...

def asUserId(
    value: str,
) -> UserId:
    """
    Brand a string as a UserId. Does not validate format, only applies type branding.

    Postconditions:
      - Return value has _brand='UserId'

    Side effects: none
    Idempotent: no
    """
    ...

def ok(
    value: any,
) -> Result:
    """
    Construct a successful Result with a value

    Postconditions:
      - result.success is true
      - result.value equals input value

    Side effects: none
    Idempotent: no
    """
    ...

def err(
    error: DomainError,
) -> Result:
    """
    Construct a failed Result with a DomainError

    Postconditions:
      - result.success is false
      - result.error equals input error

    Side effects: none
    Idempotent: no
    """
    ...

def validateLoginRequest(
    body: any,
) -> Result:
    """
    Validate and parse login request body using Zod schema

    Postconditions:
      - On success, result.value conforms to LoginRequest schema

    Errors:
      - ValidationError (InvalidInput): body does not match LoginRequest schema (missing fields, wrong types, failed validators)
          zodErrors: Zod validation error details

    Side effects: none
    Idempotent: no
    """
    ...

def validateUser(
    row: any,
) -> Result:
    """
    Validate and parse database User record using Zod schema

    Postconditions:
      - On success, result.value conforms to User schema

    Errors:
      - ValidationError (InvalidInput): row does not match User schema

    Side effects: none
    Idempotent: no
    """
    ...

def validateTask(
    row: any,
) -> Result:
    """
    Validate and parse database Task record using Zod schema

    Postconditions:
      - On success, result.value conforms to Task schema

    Errors:
      - ValidationError (InvalidInput): row does not match Task schema

    Side effects: none
    Idempotent: no
    """
    ...

def validateProject(
    row: any,
) -> Result:
    """
    Validate and parse database Project record using Zod schema

    Postconditions:
      - On success, result.value conforms to Project schema

    Errors:
      - ValidationError (InvalidInput): row does not match Project schema

    Side effects: none
    Idempotent: no
    """
    ...

def createSession(
    userId: str,
    response: NextResponse,
) -> NextResponse:
    """
    Create encrypted session cookie using iron-session. Sets HttpOnly, Secure (in production), SameSite=Lax cookie.

    Preconditions:
      - userId is non-empty

    Postconditions:
      - Session cookie is set on response
      - Session expires in 7 days

    Errors:
      - SessionEncryptionError (AuthError): Cannot encrypt session data with iron-session

    Side effects: none
    Idempotent: no
    """
    ...

def getSession(
    request: NextRequest,
) -> Result:
    """
    Decrypt and validate session cookie using iron-session

    Postconditions:
      - On success, result.value is SessionData with valid expiresAt > now

    Errors:
      - NoSessionCookie (AuthError): Request does not contain session cookie
      - SessionDecryptionError (AuthError): Cannot decrypt session cookie (tampered or wrong key)
      - SessionExpired (AuthError): Session expiresAt is in the past

    Side effects: none
    Idempotent: no
    """
    ...

def destroySession(
    response: NextResponse,
) -> NextResponse:
    """
    Clear session cookie by setting expired cookie

    Postconditions:
      - Session cookie is cleared (Max-Age=0)

    Side effects: none
    Idempotent: yes
    """
    ...

def authMiddleware(
    request: NextRequest,
) -> NextResponse:
    """
    Next.js middleware function that validates session on all protected routes. Redirects to /login if session is invalid or missing.

    Postconditions:
      - If session valid, request proceeds
      - If session invalid, redirects to /login
      - /login and /api/auth/* are always allowed

    Side effects: none
    Idempotent: no
    """
    ...

def handleLogin(
    request: NextRequest,
) -> NextResponse:
    """
    POST /api/auth/login route handler. Validates credentials, creates session, returns LoginResponse.

    Preconditions:
      - request.method is POST
      - request.body is valid JSON

    Postconditions:
      - On success, returns 200 with LoginResponse and session cookie
      - On failure, returns 401 with ApiError

    Errors:
      - InvalidCredentials (AuthError): Username or password does not match database record
      - MalformedRequest (InvalidInput): Request body does not match LoginRequest schema

    Side effects: none
    Idempotent: no
    """
    ...

def handleLogout(
    request: NextRequest,
) -> NextResponse:
    """
    POST /api/auth/logout route handler. Destroys session, returns LogoutResponse.

    Preconditions:
      - request has valid session (enforced by middleware)

    Postconditions:
      - Session cookie is cleared
      - Returns 200 with LogoutResponse

    Side effects: none
    Idempotent: yes
    """
    ...

def RootErrorBoundary(
    props: ErrorBoundaryProps,
) -> any:
    """
    React error boundary component for app-level error handling. Renders user-friendly error UI with reset button.

    Postconditions:
      - Renders error UI with error message and reset button

    Side effects: none
    Idempotent: no
    """
    ...

def PageErrorBoundary(
    props: ErrorBoundaryProps,
) -> any:
    """
    React error boundary component for page-level error handling. Similar to RootErrorBoundary but with page-specific styling.

    Postconditions:
      - Renders error UI with error message and reset button

    Side effects: none
    Idempotent: no
    """
    ...

def toApiError(
    error: DomainError,
) -> ApiError:
    """
    Convert DomainError to ApiError response structure

    Postconditions:
      - ApiError.status is appropriate HTTP status code for error.code
      - ApiError.error is error.code
      - ApiError.message is error.message

    Side effects: none
    Idempotent: no
    """
    ...

def serializeDate(
    date: any,
) -> str:
    """
    Convert Date object to ISO 8601 string for API responses (ensures no Date objects leak to JSON)

    Postconditions:
      - Return value is ISO 8601 string

    Errors:
      - InvalidDate (InvalidInput): Input is not a valid Date or ISO string

    Side effects: none
    Idempotent: no
    """
    ...

# ── REQUIRED EXPORTS ──────────────────────────────────
# Your implementation module MUST export ALL of these names
# with EXACTLY these spellings. Tests import them by name.
# __all__ = ['Database', 'MigrationResult', 'ProjectId', 'TaskId', 'UserId', 'Result', 'DomainError', 'ErrorCode', 'SessionData', 'LoginRequest', 'LoginResponse', 'LogoutResponse', 'ApiError', 'User', 'Task', 'Project', 'MigrationRecord', 'ErrorBoundaryProps', 'MiddlewareConfig', 'NextRequest', 'NextResponse', 'initDatabase', 'DatabaseError', 'runMigrations', 'MigrationError', 'closeDatabase', 'asProjectId', 'asTaskId', 'asUserId', 'ok', 'err', 'validateLoginRequest', 'InvalidInput', 'validateUser', 'validateTask', 'validateProject', 'createSession', 'AuthError', 'getSession', 'destroySession', 'authMiddleware', 'handleLogin', 'handleLogout', 'RootErrorBoundary', 'PageErrorBoundary', 'toApiError', 'serializeDate']
