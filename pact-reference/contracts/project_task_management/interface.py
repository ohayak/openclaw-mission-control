# === Project & Task Management (project_task_management) v1 ===
# CRUD API routes and UI for projects and tasks with SQLite persistence, Zod validation, SSE events, and responsive Kanban board. Handles PACT directory validation for PACT-enabled projects.

# Module invariants:
#   - All task.project_id values reference existing projects (foreign key constraint)
#   - All task.display_order values are unique within (project_id, status) groups
#   - All task.updated_at values are monotonically increasing for a given task
#   - All project.pact_directory_path values are absolute paths or null
#   - If task.assignee_type = 'unassigned', task.assignee_name must be null
#   - If task.assignee_type != 'unassigned', task.assignee_name must be non-empty string
#   - All timestamp fields are valid ISO 8601 strings
#   - All enum fields contain only defined variant values
#   - Project names are unique within the database
#   - All SSE events include version field for schema evolution
#   - Database uses PRAGMA foreign_keys = ON

class ProjectStatus(Enum):
    """Project lifecycle status"""
    active = "active"
    archived = "archived"
    paused = "paused"

class TaskStatus(Enum):
    """Task workflow status for Kanban columns"""
    backlog = "backlog"
    in_progress = "in_progress"
    review = "review"
    done = "done"

class TaskPriority(Enum):
    """Task priority levels"""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class AssigneeType(Enum):
    """Type of task assignee"""
    agent = "agent"
    human = "human"
    unassigned = "unassigned"

class SortOrder(Enum):
    """Sort direction for queries"""
    asc = "asc"
    desc = "desc"

class Project:
    """Complete project record from database"""
    id: int                                  # required, Primary key
    name: str                                # required, Project name (max 200 chars)
    description: str                         # required, Project description (max 2000 chars)
    status: ProjectStatus                    # required, Current project status
    pact_enabled: bool                       # required, Whether PACT integration is enabled
    pact_directory_path: str = None          # optional, Absolute path to PACT directory (null if not enabled)
    created_at: str                          # required, ISO 8601 timestamp
    updated_at: str                          # required, ISO 8601 timestamp for optimistic concurrency

class ProjectInsert:
    """Data for creating a new project"""
    name: str                                # required, Project name (1-200 chars)
    description: str                         # required, Project description (0-2000 chars)
    pact_enabled: bool = None                # optional, Enable PACT integration
    pact_directory_path: str = None          # optional, Path to PACT directory (required if pact_enabled)

class ProjectUpdate:
    """Data for updating an existing project"""
    name: str = None                         # optional, Updated project name
    description: str = None                  # optional, Updated description
    status: ProjectStatus = None             # optional, Updated status
    pact_enabled: bool = None                # optional, Updated PACT enabled flag
    pact_directory_path: str = None          # optional, Updated PACT directory path
    updated_at: str                          # required, Client's last known updated_at for optimistic locking

class Task:
    """Complete task record from database"""
    id: int                                  # required, Primary key
    project_id: int                          # required, Foreign key to projects table
    title: str                               # required, Task title (max 300 chars)
    description: str                         # required, Task description (max 5000 chars)
    status: TaskStatus                       # required, Current task status
    priority: TaskPriority                   # required, Task priority
    assignee_type: AssigneeType              # required, Type of assignee
    assignee_name: str = None                # optional, Name of assignee (null if unassigned)
    display_order: int                       # required, Position within status column for Kanban
    created_at: str                          # required, ISO 8601 timestamp
    updated_at: str                          # required, ISO 8601 timestamp for optimistic concurrency

class TaskInsert:
    """Data for creating a new task"""
    project_id: int                          # required, Parent project ID
    title: str                               # required, Task title (1-300 chars)
    description: str                         # required, Task description (0-5000 chars)
    status: TaskStatus = None                # optional, Initial status (default: backlog)
    priority: TaskPriority = None            # optional, Task priority (default: medium)
    assignee_type: AssigneeType = None       # optional, Assignee type (default: unassigned)
    assignee_name: str = None                # optional, Assignee name (required if assignee_type != unassigned)

class TaskUpdate:
    """Data for updating an existing task"""
    title: str = None                        # optional, Updated task title
    description: str = None                  # optional, Updated description
    status: TaskStatus = None                # optional, Updated status (validated)
    priority: TaskPriority = None            # optional, Updated priority
    assignee_type: AssigneeType = None       # optional, Updated assignee type
    assignee_name: str = None                # optional, Updated assignee name
    display_order: int = None                # optional, Updated display order for drag-and-drop
    updated_at: str                          # required, Client's last known updated_at for optimistic locking

class PaginationParams:
    """Pagination and sorting parameters"""
    page: int = None                         # optional, Page number (1-indexed, default: 1)
    page_size: int = None                    # optional, Items per page (1-100, default: 50)
    sort_by: str = None                      # optional, Field to sort by
    sort_order: SortOrder = None             # optional, Sort direction (default: desc)

class PaginatedResponse:
    """Generic paginated response wrapper"""
    items: list                              # required, Items for current page
    total: int                               # required, Total item count
    page: int                                # required, Current page number
    page_size: int                           # required, Items per page
    total_pages: int                         # required, Total number of pages

class TaskFilterParams:
    """Filtering parameters for task queries"""
    project_id: int = None                   # optional, Filter by project
    status: TaskStatus = None                # optional, Filter by status
    priority: TaskPriority = None            # optional, Filter by priority
    assignee_type: AssigneeType = None       # optional, Filter by assignee type
    assignee_name: str = None                # optional, Filter by assignee name

class PactDirectoryValidation:
    """Result of PACT directory structure validation"""
    valid: bool                              # required, Whether structure is valid
    resolved_path: str                       # required, Absolute resolved path
    errors: list                             # required, List of validation error messages

class StatusTransitionValidation:
    """Result of task status transition validation"""
    valid: bool                              # required, Whether transition is allowed
    error_message: str = None                # optional, Error message if invalid

class ErrorResponse:
    """Standard API error response shape"""
    error: str                               # required, Error type (e.g., 'validation_error')
    message: str                             # required, Human-readable error message
    details: dict = None                     # optional, Additional error context (field errors, etc.)
    timestamp: str                           # required, ISO 8601 timestamp

class TaskStatusChangedEvent:
    """SSE event for task status changes"""
    type: str                                # required, Event type: 'task_status_changed'
    task_id: int                             # required, ID of changed task
    project_id: int                          # required, Parent project ID
    old_status: TaskStatus                   # required, Previous status
    new_status: TaskStatus                   # required, New status
    timestamp: str                           # required, ISO 8601 timestamp
    version: int                             # required, Event schema version

class TaskCreatedEvent:
    """SSE event for task creation"""
    type: str                                # required, Event type: 'task_created'
    task_id: int                             # required, ID of created task
    project_id: int                          # required, Parent project ID
    task: Task                               # required, Full task object
    timestamp: str                           # required, ISO 8601 timestamp
    version: int                             # required, Event schema version

class TaskUpdatedEvent:
    """SSE event for task updates"""
    type: str                                # required, Event type: 'task_updated'
    task_id: int                             # required, ID of updated task
    project_id: int                          # required, Parent project ID
    task: Task                               # required, Full updated task object
    timestamp: str                           # required, ISO 8601 timestamp
    version: int                             # required, Event schema version

class TaskDeletedEvent:
    """SSE event for task deletion"""
    type: str                                # required, Event type: 'task_deleted'
    task_id: int                             # required, ID of deleted task
    project_id: int                          # required, Parent project ID
    timestamp: str                           # required, ISO 8601 timestamp
    version: int                             # required, Event schema version

class ProjectCostSummary:
    """Cost breakdown for a project"""
    project_id: int                          # required, Project ID
    total_cost_usd: float                    # required, Total cost in USD
    total_tokens: int                        # required, Total tokens consumed
    task_count: int                          # required, Number of associated tasks
    period_start: str = None                 # optional, Start of cost period (ISO 8601)
    period_end: str = None                   # optional, End of cost period (ISO 8601)

def list_projects(
    pagination: PaginationParams = None,
    status_filter: ProjectStatus = None,
) -> PaginatedResponse:
    """
    Retrieve paginated list of projects with optional filtering and sorting

    Preconditions:
      - pagination.page >= 1
      - pagination.page_size between 1 and 100
      - Database connection is available

    Postconditions:
      - Returns projects ordered by sort criteria
      - total reflects filtered count
      - items.length <= page_size

    Errors:
      - database_error (DatabaseError): SQLite query fails
      - invalid_sort_field (ValidationError): sort_by references non-existent column

    Side effects: none
    Idempotent: no
    """
    ...

def get_project(
    project_id: int,
) -> Project:
    """
    Retrieve a single project by ID

    Preconditions:
      - project_id > 0

    Postconditions:
      - Returns project with matching ID
      - All timestamps are valid ISO 8601 strings

    Errors:
      - not_found (NotFoundError): No project exists with given ID
      - database_error (DatabaseError): SQLite query fails

    Side effects: none
    Idempotent: no
    """
    ...

def create_project(
    project_data: ProjectInsert,
) -> Project:
    """
    Create a new project with optional PACT integration. Validates PACT directory if enabled.

    Preconditions:
      - project_data.name length between 1 and 200
      - project_data.description length <= 2000
      - If pact_enabled is true, pact_directory_path must be provided
      - If pact_directory_path provided, must pass validatePactDirectory

    Postconditions:
      - New project inserted into database
      - Returns project with generated ID and timestamps
      - pact_directory_path is stored as absolute resolved path if provided

    Errors:
      - validation_error (ValidationError): Input fails Zod schema validation
      - invalid_pact_directory (ValidationError): PACT directory validation fails
          validation_errors: list[str]
      - duplicate_name (ConflictError): Project with same name already exists
      - database_error (DatabaseError): SQLite insert fails

    Side effects: none
    Idempotent: no
    """
    ...

def update_project(
    project_id: int,
    update_data: ProjectUpdate,
) -> Project:
    """
    Update an existing project with optimistic concurrency control

    Preconditions:
      - project_id > 0
      - update_data.updated_at matches current database value
      - If pact_enabled changed to true, pact_directory_path must be valid
      - At least one field (other than updated_at) must be provided

    Postconditions:
      - Project updated in database
      - updated_at timestamp is refreshed
      - Returns updated project

    Errors:
      - not_found (NotFoundError): No project exists with given ID
      - conflict (ConflictError): updated_at does not match (concurrent modification)
          current_version: str
      - validation_error (ValidationError): Input fails Zod schema validation
      - invalid_pact_directory (ValidationError): PACT directory validation fails
      - database_error (DatabaseError): SQLite update fails

    Side effects: none
    Idempotent: no
    """
    ...

def delete_project(
    project_id: int,
) -> bool:
    """
    Delete a project and all associated tasks (cascading delete)

    Preconditions:
      - project_id > 0

    Postconditions:
      - Project removed from database
      - All associated tasks are deleted (foreign key cascade)
      - Returns true on successful deletion

    Errors:
      - not_found (NotFoundError): No project exists with given ID
      - database_error (DatabaseError): SQLite delete fails

    Side effects: none
    Idempotent: no
    """
    ...

def list_tasks(
    pagination: PaginationParams = None,
    filters: TaskFilterParams = None,
) -> PaginatedResponse:
    """
    Retrieve paginated list of tasks with filtering and sorting

    Preconditions:
      - pagination.page >= 1
      - pagination.page_size between 1 and 100
      - If filters.project_id provided, project must exist

    Postconditions:
      - Returns tasks matching filter criteria
      - Tasks ordered by display_order within status columns when sorted by status
      - total reflects filtered count

    Errors:
      - database_error (DatabaseError): SQLite query fails
      - invalid_sort_field (ValidationError): sort_by references non-existent column

    Side effects: none
    Idempotent: no
    """
    ...

def get_task(
    task_id: int,
) -> Task:
    """
    Retrieve a single task by ID

    Preconditions:
      - task_id > 0

    Postconditions:
      - Returns task with matching ID
      - All timestamps are valid ISO 8601 strings

    Errors:
      - not_found (NotFoundError): No task exists with given ID
      - database_error (DatabaseError): SQLite query fails

    Side effects: none
    Idempotent: no
    """
    ...

def create_task(
    task_data: TaskInsert,
) -> Task:
    """
    Create a new task and publish TaskCreatedEvent to SSE bus

    Preconditions:
      - task_data.project_id references existing project
      - task_data.title length between 1 and 300
      - task_data.description length <= 5000
      - If assignee_type != unassigned, assignee_name must be provided

    Postconditions:
      - New task inserted into database
      - Returns task with generated ID and timestamps
      - display_order set to max + 1 within status column
      - TaskCreatedEvent published to SSE bus

    Errors:
      - validation_error (ValidationError): Input fails Zod schema validation
      - foreign_key_violation (ValidationError): project_id does not exist
      - database_error (DatabaseError): SQLite insert fails
      - sse_publish_error (InternalError): SSE event publish fails

    Side effects: none
    Idempotent: no
    """
    ...

def update_task(
    task_id: int,
    update_data: TaskUpdate,
) -> Task:
    """
    Update an existing task with optimistic concurrency control. Publishes TaskUpdatedEvent or TaskStatusChangedEvent.

    Preconditions:
      - task_id > 0
      - update_data.updated_at matches current database value
      - If status changed, validateStatusTransition must pass
      - If assignee_type changed to agent/human, assignee_name must be provided
      - At least one field (other than updated_at) must be provided

    Postconditions:
      - Task updated in database
      - updated_at timestamp is refreshed
      - If status changed, TaskStatusChangedEvent published
      - TaskUpdatedEvent published to SSE bus
      - Returns updated task

    Errors:
      - not_found (NotFoundError): No task exists with given ID
      - conflict (ConflictError): updated_at does not match (concurrent modification)
          current_version: str
      - validation_error (ValidationError): Input fails Zod schema validation
      - invalid_status_transition (ConflictError): Status transition not allowed
          allowed_transitions: list[str]
      - database_error (DatabaseError): SQLite update fails
      - sse_publish_error (InternalError): SSE event publish fails

    Side effects: none
    Idempotent: no
    """
    ...

def delete_task(
    task_id: int,
) -> bool:
    """
    Delete a task and publish TaskDeletedEvent to SSE bus

    Preconditions:
      - task_id > 0

    Postconditions:
      - Task removed from database
      - TaskDeletedEvent published to SSE bus
      - Returns true on successful deletion

    Errors:
      - not_found (NotFoundError): No task exists with given ID
      - database_error (DatabaseError): SQLite delete fails
      - sse_publish_error (InternalError): SSE event publish fails

    Side effects: none
    Idempotent: no
    """
    ...

def reorder_tasks(
    task_orders: list,
) -> bool:
    """
    Bulk update display_order for tasks in Kanban column (drag-and-drop support)

    Preconditions:
      - All task_ids must exist
      - All tasks belong to same project and status column
      - display_order values are unique within update set

    Postconditions:
      - All specified tasks have updated display_order
      - updated_at timestamps refreshed for all affected tasks
      - Returns true on success

    Errors:
      - validation_error (ValidationError): Input validation fails
      - conflict (ConflictError): Any updated_at does not match
      - not_found (NotFoundError): Any task_id does not exist
      - database_error (DatabaseError): SQLite transaction fails

    Side effects: none
    Idempotent: no
    """
    ...

def validate_pact_directory(
    directory_path: str,
) -> PactDirectoryValidation:
    """
    Validate PACT directory structure (.pact/ subdirectory and pact.yaml file)

    Preconditions:
      - directory_path is non-empty string

    Postconditions:
      - Returns validation result with resolved absolute path
      - errors list contains specific missing/invalid items
      - valid is true only if .pact/ exists and pact.yaml is readable

    Errors:
      - filesystem_error (FilesystemError): Path resolution or access check fails

    Side effects: none
    Idempotent: no
    """
    ...

def validate_status_transition(
    from_status: TaskStatus,
    to_status: TaskStatus,
) -> StatusTransitionValidation:
    """
    Validate whether a task status transition is allowed

    Preconditions:
      - from_status and to_status are valid TaskStatus values

    Postconditions:
      - Returns validation result
      - Allowed transitions: backlog -> in_progress, in_progress -> review|backlog, review -> done|in_progress, done -> backlog
      - error_message provided if valid is false

    Side effects: none
    Idempotent: no
    """
    ...

def get_project_cost_summary(
    project_id: int,
    period_start: str = None,
    period_end: str = None,
) -> ProjectCostSummary:
    """
    Retrieve cost breakdown for a project over optional time period

    Preconditions:
      - project_id > 0
      - If period_start provided, must be valid ISO 8601
      - If period_end provided, must be >= period_start

    Postconditions:
      - Returns aggregated cost data from agent activity logs
      - total_cost_usd is sum of all costs in period
      - total_tokens is sum of all tokens consumed
      - task_count reflects associated tasks

    Errors:
      - not_found (NotFoundError): Project does not exist
      - validation_error (ValidationError): Invalid timestamp format
      - database_error (DatabaseError): SQLite query fails

    Side effects: none
    Idempotent: no
    """
    ...

def bad_request(
    message: str,
    details: dict = None,
) -> ErrorResponse:
    """
    Create a 400 Bad Request error response

    Postconditions:
      - Returns ErrorResponse with error='validation_error'
      - timestamp is current ISO 8601 time

    Side effects: none
    Idempotent: no
    """
    ...

def not_found(
    resource_type: str,
    resource_id: int,
) -> ErrorResponse:
    """
    Create a 404 Not Found error response

    Postconditions:
      - Returns ErrorResponse with error='not_found'
      - message includes resource type and ID

    Side effects: none
    Idempotent: no
    """
    ...

def conflict(
    message: str,
    details: dict = None,
) -> ErrorResponse:
    """
    Create a 409 Conflict error response

    Postconditions:
      - Returns ErrorResponse with error='conflict'
      - details includes conflict resolution hints

    Side effects: none
    Idempotent: no
    """
    ...

def server_error(
    message: str,
    log_details: str = None,
) -> ErrorResponse:
    """
    Create a 500 Internal Server Error response

    Postconditions:
      - Returns ErrorResponse with error='internal_error'
      - log_details written to server logs but not included in response

    Side effects: none
    Idempotent: no
    """
    ...

def publish_task_event(
    event: dict,
) -> bool:
    """
    Publish a task-related event to SSE bus with heartbeat support

    Preconditions:
      - event has required fields for its type
      - event.version is set to current schema version (1)

    Postconditions:
      - Event published to SSE bus
      - All connected clients receive event if subscribed
      - Returns true on success

    Errors:
      - serialization_error (InternalError): Event cannot be serialized to JSON
      - bus_error (InternalError): SSE bus is unavailable

    Side effects: none
    Idempotent: no
    """
    ...

# ── REQUIRED EXPORTS ──────────────────────────────────
# Your implementation module MUST export ALL of these names
# with EXACTLY these spellings. Tests import them by name.
# __all__ = ['ProjectStatus', 'TaskStatus', 'TaskPriority', 'AssigneeType', 'SortOrder', 'Project', 'ProjectInsert', 'ProjectUpdate', 'Task', 'TaskInsert', 'TaskUpdate', 'PaginationParams', 'PaginatedResponse', 'TaskFilterParams', 'PactDirectoryValidation', 'StatusTransitionValidation', 'ErrorResponse', 'TaskStatusChangedEvent', 'TaskCreatedEvent', 'TaskUpdatedEvent', 'TaskDeletedEvent', 'ProjectCostSummary', 'list_projects', 'DatabaseError', 'ValidationError', 'get_project', 'NotFoundError', 'create_project', 'ConflictError', 'update_project', 'delete_project', 'list_tasks', 'get_task', 'create_task', 'InternalError', 'update_task', 'delete_task', 'reorder_tasks', 'validate_pact_directory', 'FilesystemError', 'validate_status_transition', 'get_project_cost_summary', 'bad_request', 'not_found', 'conflict', 'server_error', 'publish_task_event']
