"""
Project & Task Management Component
CRUD API for projects and tasks with SQLite persistence, validation, SSE events, and Kanban board support.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field


# ============================================================================
# ENUMS
# ============================================================================

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


# ============================================================================
# EXCEPTION CLASSES
# ============================================================================

class DatabaseError(Exception):
    """Database operation failed"""
    pass


class ValidationError(Exception):
    """Input validation failed"""
    pass


class NotFoundError(Exception):
    """Resource not found"""
    pass


class ConflictError(Exception):
    """Resource conflict (optimistic locking, duplicate, etc.)"""
    pass


class InternalError(Exception):
    """Internal server error"""
    pass


class FilesystemError(Exception):
    """Filesystem operation failed"""
    pass


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Project:
    """Complete project record from database"""
    id: int
    name: str
    description: str
    status: str
    pact_enabled: bool
    pact_directory_path: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class ProjectInsert:
    """Data for creating a new project"""
    name: str
    description: str
    pact_enabled: Optional[bool] = False
    pact_directory_path: Optional[str] = None


@dataclass
class ProjectUpdate:
    """Data for updating an existing project"""
    updated_at: str
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    pact_enabled: Optional[bool] = None
    pact_directory_path: Optional[str] = None


@dataclass
class Task:
    """Complete task record from database"""
    id: int
    project_id: int
    title: str
    description: str
    status: str
    priority: str
    assignee_type: str
    assignee_name: Optional[str]
    display_order: int
    created_at: str
    updated_at: str


@dataclass
class TaskInsert:
    """Data for creating a new task"""
    project_id: int
    title: str
    description: str
    status: Optional[str] = "backlog"
    priority: Optional[str] = "medium"
    assignee_type: Optional[str] = "unassigned"
    assignee_name: Optional[str] = None


@dataclass
class TaskUpdate:
    """Data for updating an existing task"""
    updated_at: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_type: Optional[str] = None
    assignee_name: Optional[str] = None
    display_order: Optional[int] = None


@dataclass
class PaginationParams:
    """Pagination and sorting parameters"""
    page: Optional[int] = 1
    page_size: Optional[int] = 50
    sort_by: Optional[str] = "created_at"
    sort_order: Optional[str] = "desc"


@dataclass
class PaginatedResponse:
    """Generic paginated response wrapper"""
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass
class TaskFilterParams:
    """Filtering parameters for task queries"""
    project_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_type: Optional[str] = None
    assignee_name: Optional[str] = None


@dataclass
class PactDirectoryValidation:
    """Result of PACT directory structure validation"""
    valid: bool
    resolved_path: str
    errors: List[str]


@dataclass
class StatusTransitionValidation:
    """Result of task status transition validation"""
    valid: bool
    error_message: Optional[str] = None


@dataclass
class ErrorResponse:
    """Standard API error response shape"""
    error: str
    message: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class TaskStatusChangedEvent:
    """SSE event for task status changes"""
    type: str
    task_id: int
    project_id: int
    old_status: str
    new_status: str
    timestamp: str
    version: int


@dataclass
class TaskCreatedEvent:
    """SSE event for task creation"""
    type: str
    task_id: int
    project_id: int
    task: Dict[str, Any]
    timestamp: str
    version: int


@dataclass
class TaskUpdatedEvent:
    """SSE event for task updates"""
    type: str
    task_id: int
    project_id: int
    task: Dict[str, Any]
    timestamp: str
    version: int


@dataclass
class TaskDeletedEvent:
    """SSE event for task deletion"""
    type: str
    task_id: int
    project_id: int
    timestamp: str
    version: int


@dataclass
class ProjectCostSummary:
    """Cost breakdown for a project"""
    project_id: int
    total_cost_usd: float
    total_tokens: int
    task_count: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None


# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db_connection():
    """Get or create database connection"""
    db_path = os.environ.get('DATABASE_PATH', '/tmp/mission_control.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def validate_pagination(pagination: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate and normalize pagination parameters"""
    if pagination is None:
        pagination = {}

    page = pagination.get('page', 1)
    page_size = pagination.get('page_size', 50)
    sort_by = pagination.get('sort_by', 'created_at')
    sort_order = pagination.get('sort_order', 'desc')

    if page < 1:
        raise ValidationError(bad_request("Page must be >= 1"))

    if page_size < 1 or page_size > 100:
        raise ValidationError(bad_request("Page size must be between 1 and 100"))

    return {
        'page': page,
        'page_size': page_size,
        'sort_by': sort_by,
        'sort_order': sort_order
    }


def validate_project_insert(data: Dict[str, Any]):
    """Validate project insert data"""
    name = data.get('name', '')
    description = data.get('description', '')
    pact_enabled = data.get('pact_enabled', False)
    pact_directory_path = data.get('pact_directory_path')

    if not name or len(name) < 1 or len(name) > 200:
        raise ValidationError(bad_request("Project name must be 1-200 characters"))

    if len(description) > 2000:
        raise ValidationError(bad_request("Project description must be <= 2000 characters"))

    if pact_enabled and not pact_directory_path:
        raise ValidationError(bad_request("PACT directory path required when PACT is enabled"))

    if pact_directory_path:
        validation = validate_pact_directory(pact_directory_path)
        if not validation['valid']:
            error_details = {
                'validation_errors': validation['errors']
            }
            raise ValidationError({
                'error': 'invalid_pact_directory',
                'message': 'PACT directory validation failed',
                'details': error_details,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })


def validate_task_insert(data: Dict[str, Any]):
    """Validate task insert data"""
    title = data.get('title', '')
    description = data.get('description', '')
    assignee_type = data.get('assignee_type', 'unassigned')
    assignee_name = data.get('assignee_name')

    if not title or len(title) < 1 or len(title) > 300:
        raise ValidationError(bad_request("Task title must be 1-300 characters"))

    if len(description) > 5000:
        raise ValidationError(bad_request("Task description must be <= 5000 characters"))

    if assignee_type in ('agent', 'human') and not assignee_name:
        raise ValidationError(bad_request("Assignee name required for agent/human assignee type"))


def validate_id(resource_id: int, resource_type: str = "resource"):
    """Validate resource ID"""
    if resource_id <= 0:
        raise ValidationError(bad_request(f"Invalid {resource_type} ID"))


# ============================================================================
# ERROR RESPONSE BUILDERS
# ============================================================================

def bad_request(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a 400 Bad Request error response"""
    return {
        'error': 'validation_error',
        'message': message,
        'details': details,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


def not_found(resource_type: str, resource_id: int) -> Dict[str, Any]:
    """Create a 404 Not Found error response"""
    return {
        'error': 'not_found',
        'message': f'{resource_type} with ID {resource_id} not found',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


def conflict(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a 409 Conflict error response"""
    return {
        'error': 'conflict',
        'message': message,
        'details': details,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


def server_error(message: str, log_details: Optional[str] = None) -> Dict[str, Any]:
    """Create a 500 Internal Server Error response"""
    if log_details:
        # In a real implementation, log this
        pass
    return {
        'error': 'internal_error',
        'message': message,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


# ============================================================================
# PROJECT CRUD OPERATIONS
# ============================================================================

def list_projects(
    pagination: Optional[Dict[str, Any]] = None,
    status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve paginated list of projects with optional filtering and sorting"""
    try:
        params = validate_pagination(pagination)
    except ValidationError as e:
        raise e

    try:
        db = get_db_connection()

        # Build query
        where_clauses = []
        query_params = []

        if status_filter:
            where_clauses.append("status = ?")
            query_params.append(status_filter)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Validate sort field
        valid_sort_fields = ['id', 'name', 'created_at', 'updated_at', 'status']
        if params['sort_by'] not in valid_sort_fields:
            raise Exception({'error': 'invalid_sort_field'})

        # Count total
        count_query = f"SELECT COUNT(*) as count FROM projects {where_sql}"
        cursor = db.execute(count_query, query_params)
        count_row = cursor.fetchone()
        total = count_row[0] if count_row else 0
        cursor.close()

        # Fetch page
        offset = (params['page'] - 1) * params['page_size']
        sort_sql = f"ORDER BY {params['sort_by']} {params['sort_order'].upper()}"
        query = f"SELECT * FROM projects {where_sql} {sort_sql} LIMIT ? OFFSET ?"
        query_params.extend([params['page_size'], offset])

        cursor = db.execute(query, query_params)
        rows = cursor.fetchall()
        cursor.close()

        items = [dict(row) for row in rows]

        total_pages = (total + params['page_size'] - 1) // params['page_size']

        return {
            'items': items,
            'total': total,
            'page': params['page'],
            'page_size': params['page_size'],
            'total_pages': total_pages
        }

    except Exception as e:
        if isinstance(e.args[0], dict) and e.args[0].get('error') == 'invalid_sort_field':
            raise e
        raise DatabaseError(server_error("Database query failed"))


def get_project(project_id: int) -> Dict[str, Any]:
    """Retrieve a single project by ID"""
    validate_id(project_id, "project")

    try:
        db = get_db_connection()
        cursor = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        cursor.close()

        if not row:
            raise NotFoundError(not_found("Project", project_id))

        return dict(row)

    except NotFoundError:
        raise
    except Exception as e:
        raise DatabaseError(server_error("Database query failed"))


def create_project(project_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new project with optional PACT integration"""
    validate_project_insert(project_data)

    try:
        db = get_db_connection()

        # Check for duplicate name
        cursor = db.execute("SELECT id FROM projects WHERE name = ?", (project_data['name'],))
        if cursor.fetchone():
            cursor.close()
            raise ConflictError({
                'error': 'duplicate_name',
                'message': 'Project with this name already exists',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        cursor.close()

        # Resolve PACT directory path if provided
        pact_path = project_data.get('pact_directory_path', '')
        if pact_path:
            validation = validate_pact_directory(pact_path)
            pact_path = validation['resolved_path']

        now = datetime.now(timezone.utc).isoformat()

        cursor = db.execute(
            """
            INSERT INTO projects (name, description, status, pact_enabled, pact_directory_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_data['name'],
                project_data.get('description', ''),
                'active',
                project_data.get('pact_enabled', False),
                pact_path,
                now,
                now
            )
        )

        project_id = cursor.lastrowid
        db.commit()
        cursor.close()

        return get_project(project_id)

    except (ValidationError, ConflictError):
        raise
    except Exception as e:
        raise DatabaseError(server_error("Database insert failed"))


def update_project(project_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing project with optimistic concurrency control"""
    validate_id(project_id, "project")

    try:
        db = get_db_connection()

        # Get current project
        current = get_project(project_id)

        # Check optimistic lock
        if update_data.get('updated_at') != current['updated_at']:
            raise ConflictError(conflict(
                "Concurrent modification detected",
                {'current_version': current['updated_at']}
            ))

        # Build update query
        set_clauses = []
        params = []

        if 'name' in update_data and update_data['name'] is not None:
            set_clauses.append("name = ?")
            params.append(update_data['name'])

        if 'description' in update_data and update_data['description'] is not None:
            set_clauses.append("description = ?")
            params.append(update_data['description'])

        if 'status' in update_data and update_data['status'] is not None:
            set_clauses.append("status = ?")
            params.append(update_data['status'])

        if 'pact_enabled' in update_data and update_data['pact_enabled'] is not None:
            set_clauses.append("pact_enabled = ?")
            params.append(update_data['pact_enabled'])

            # Validate PACT directory if enabling
            if update_data['pact_enabled'] and update_data.get('pact_directory_path'):
                validation = validate_pact_directory(update_data['pact_directory_path'])
                if not validation['valid']:
                    raise ValidationError({
                        'error': 'invalid_pact_directory',
                        'message': 'PACT directory validation failed',
                        'details': {'validation_errors': validation['errors']},
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })

        if 'pact_directory_path' in update_data and update_data['pact_directory_path'] is not None:
            validation = validate_pact_directory(update_data['pact_directory_path'])
            set_clauses.append("pact_directory_path = ?")
            params.append(validation['resolved_path'])

        if not set_clauses:
            return current

        # Update timestamp
        now = datetime.now(timezone.utc).isoformat()
        set_clauses.append("updated_at = ?")
        params.append(now)

        params.append(project_id)

        query = f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ?"
        db.execute(query, params)
        db.commit()

        return get_project(project_id)

    except (NotFoundError, ConflictError, ValidationError):
        raise
    except Exception as e:
        raise DatabaseError(server_error("Database update failed"))


def delete_project(project_id: int) -> bool:
    """Delete a project and all associated tasks (cascading delete)"""
    validate_id(project_id, "project")

    try:
        db = get_db_connection()

        # Check if project exists
        get_project(project_id)

        # Delete project (cascade will handle tasks)
        db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        db.commit()

        return True

    except NotFoundError:
        raise
    except Exception as e:
        raise DatabaseError(server_error("Database delete failed"))


# ============================================================================
# TASK CRUD OPERATIONS
# ============================================================================

def list_tasks(
    pagination: Optional[Dict[str, Any]] = None,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Retrieve paginated list of tasks with filtering and sorting"""
    try:
        params = validate_pagination(pagination)
    except ValidationError as e:
        raise e

    if filters is None:
        filters = {}

    try:
        db = get_db_connection()

        # Build query
        where_clauses = []
        query_params = []

        if filters.get('project_id'):
            where_clauses.append("project_id = ?")
            query_params.append(filters['project_id'])

        if filters.get('status'):
            where_clauses.append("status = ?")
            query_params.append(filters['status'])

        if filters.get('priority'):
            where_clauses.append("priority = ?")
            query_params.append(filters['priority'])

        if filters.get('assignee_type'):
            where_clauses.append("assignee_type = ?")
            query_params.append(filters['assignee_type'])

        if filters.get('assignee_name'):
            where_clauses.append("assignee_name = ?")
            query_params.append(filters['assignee_name'])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Validate sort field
        valid_sort_fields = ['id', 'title', 'created_at', 'updated_at', 'status', 'priority', 'display_order']
        if params['sort_by'] not in valid_sort_fields:
            raise Exception({'error': 'invalid_sort_field'})

        # Count total
        count_query = f"SELECT COUNT(*) as count FROM tasks {where_sql}"
        cursor = db.execute(count_query, query_params)
        count_row = cursor.fetchone()
        total = count_row[0] if count_row else 0
        cursor.close()

        # Fetch page
        offset = (params['page'] - 1) * params['page_size']
        sort_sql = f"ORDER BY {params['sort_by']} {params['sort_order'].upper()}"
        query = f"SELECT * FROM tasks {where_sql} {sort_sql} LIMIT ? OFFSET ?"
        query_params.extend([params['page_size'], offset])

        cursor = db.execute(query, query_params)
        rows = cursor.fetchall()
        cursor.close()

        items = [dict(row) for row in rows]

        total_pages = (total + params['page_size'] - 1) // params['page_size']

        return {
            'items': items,
            'total': total,
            'page': params['page'],
            'page_size': params['page_size'],
            'total_pages': total_pages
        }

    except Exception as e:
        if isinstance(e.args[0], dict) and e.args[0].get('error') == 'invalid_sort_field':
            raise e
        raise DatabaseError(server_error("Database query failed"))


def get_task(task_id: int) -> Dict[str, Any]:
    """Retrieve a single task by ID"""
    validate_id(task_id, "task")

    try:
        db = get_db_connection()
        cursor = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        cursor.close()

        if not row:
            raise NotFoundError(not_found("Task", task_id))

        return dict(row)

    except NotFoundError:
        raise
    except Exception as e:
        raise DatabaseError(server_error("Database query failed"))


def create_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new task and publish TaskCreatedEvent to SSE bus"""
    validate_task_insert(task_data)

    try:
        db = get_db_connection()

        # Check if project exists
        try:
            get_project(task_data['project_id'])
        except NotFoundError:
            raise ValidationError({
                'error': 'foreign_key_violation',
                'message': 'Project does not exist',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

        # Get max display_order for status
        status = task_data.get('status', 'backlog')
        cursor = db.execute(
            "SELECT MAX(display_order) as max_order FROM tasks WHERE project_id = ? AND status = ?",
            (task_data['project_id'], status)
        )
        row = cursor.fetchone()
        max_order = row[0] if row and row[0] is not None else 0
        cursor.close()

        display_order = max_order + 1
        now = datetime.now(timezone.utc).isoformat()

        cursor = db.execute(
            """
            INSERT INTO tasks (project_id, title, description, status, priority, assignee_type, assignee_name, display_order, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_data['project_id'],
                task_data['title'],
                task_data.get('description', ''),
                status,
                task_data.get('priority', 'medium'),
                task_data.get('assignee_type', 'unassigned'),
                task_data.get('assignee_name'),
                display_order,
                now,
                now
            )
        )

        task_id = cursor.lastrowid
        db.commit()
        cursor.close()

        task = get_task(task_id)

        # Publish TaskCreatedEvent
        event = {
            'type': 'task_created',
            'task_id': task_id,
            'project_id': task_data['project_id'],
            'task': task,
            'timestamp': now,
            'version': 1
        }
        publish_task_event(event)

        return task

    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        raise DatabaseError(server_error("Database insert failed"))


def update_task(task_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing task with optimistic concurrency control"""
    validate_id(task_id, "task")

    try:
        db = get_db_connection()

        # Get current task
        current = get_task(task_id)

        # Check optimistic lock
        if update_data.get('updated_at') != current['updated_at']:
            raise ConflictError(conflict(
                "Concurrent modification detected",
                {'current_version': current['updated_at']}
            ))

        # Build update query
        set_clauses = []
        params = []
        status_changed = False
        old_status = current['status']
        new_status = old_status

        if 'title' in update_data and update_data['title'] is not None:
            set_clauses.append("title = ?")
            params.append(update_data['title'])

        if 'description' in update_data and update_data['description'] is not None:
            set_clauses.append("description = ?")
            params.append(update_data['description'])

        if 'status' in update_data and update_data['status'] is not None:
            new_status = update_data['status']
            if new_status != old_status:
                # Validate status transition
                validation = validate_status_transition(old_status, new_status)
                if not validation['valid']:
                    raise ConflictError({
                        'error': 'invalid_status_transition',
                        'message': validation['error_message'],
                        'details': {'allowed_transitions': get_allowed_transitions(old_status)},
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                status_changed = True

            set_clauses.append("status = ?")
            params.append(new_status)

        if 'priority' in update_data and update_data['priority'] is not None:
            set_clauses.append("priority = ?")
            params.append(update_data['priority'])

        if 'assignee_type' in update_data and update_data['assignee_type'] is not None:
            assignee_type = update_data['assignee_type']
            assignee_name = update_data.get('assignee_name')

            if assignee_type in ('agent', 'human') and not assignee_name:
                raise ValidationError(bad_request("Assignee name required for agent/human assignee type"))

            set_clauses.append("assignee_type = ?")
            params.append(assignee_type)

        if 'assignee_name' in update_data:
            set_clauses.append("assignee_name = ?")
            params.append(update_data['assignee_name'])

        if 'display_order' in update_data and update_data['display_order'] is not None:
            set_clauses.append("display_order = ?")
            params.append(update_data['display_order'])

        if not set_clauses:
            return current

        # Update timestamp
        now = datetime.now(timezone.utc).isoformat()
        set_clauses.append("updated_at = ?")
        params.append(now)

        params.append(task_id)

        query = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
        db.execute(query, params)
        db.commit()

        task = get_task(task_id)

        # Publish events
        if status_changed:
            event = {
                'type': 'task_status_changed',
                'task_id': task_id,
                'project_id': current['project_id'],
                'old_status': old_status,
                'new_status': new_status,
                'timestamp': now,
                'version': 1
            }
            publish_task_event(event)

        event = {
            'type': 'task_updated',
            'task_id': task_id,
            'project_id': current['project_id'],
            'task': task,
            'timestamp': now,
            'version': 1
        }
        publish_task_event(event)

        return task

    except (NotFoundError, ConflictError, ValidationError):
        raise
    except Exception as e:
        raise DatabaseError(server_error("Database update failed"))


def delete_task(task_id: int) -> bool:
    """Delete a task and publish TaskDeletedEvent to SSE bus"""
    validate_id(task_id, "task")

    try:
        db = get_db_connection()

        # Get task to publish event
        task = get_task(task_id)

        # Delete task
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()

        # Publish TaskDeletedEvent
        event = {
            'type': 'task_deleted',
            'task_id': task_id,
            'project_id': task['project_id'],
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'version': 1
        }
        publish_task_event(event)

        return True

    except NotFoundError:
        raise
    except Exception as e:
        raise DatabaseError(server_error("Database delete failed"))


def reorder_tasks(task_orders: List[Dict[str, Any]]) -> bool:
    """Bulk update display_order for tasks in Kanban column"""
    try:
        db = get_db_connection()

        if not task_orders:
            return True

        # Validate all tasks exist and belong to same project/status
        task_ids = [item['task_id'] for item in task_orders]
        tasks = [get_task(tid) for tid in task_ids]

        project_ids = set(t['project_id'] for t in tasks)
        statuses = set(t['status'] for t in tasks)

        if len(project_ids) > 1:
            raise ValidationError(bad_request("All tasks must belong to the same project"))

        if len(statuses) > 1:
            raise ValidationError(bad_request("All tasks must have the same status"))

        # Update display orders
        now = datetime.now(timezone.utc).isoformat()
        for item in task_orders:
            db.execute(
                "UPDATE tasks SET display_order = ?, updated_at = ? WHERE id = ?",
                (item['display_order'], now, item['task_id'])
            )

        db.commit()
        return True

    except (NotFoundError, ValidationError):
        raise
    except Exception as e:
        raise DatabaseError(server_error("Database transaction failed"))


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_pact_directory(directory_path: str) -> Dict[str, Any]:
    """Validate PACT directory structure (.pact/ subdirectory and pact.yaml file)"""
    try:
        path = Path(directory_path).resolve()
        resolved_path = str(path)
        errors = []

        if not path.exists():
            errors.append(f"Directory does not exist: {resolved_path}")
        else:
            pact_subdir = path / '.pact'
            if not pact_subdir.exists():
                errors.append(".pact/ subdirectory missing")

            pact_yaml = path / 'pact.yaml'
            if not pact_yaml.exists():
                errors.append("pact.yaml file missing")
            elif not pact_yaml.is_file():
                errors.append("pact.yaml is not a file")

        return {
            'valid': len(errors) == 0,
            'resolved_path': resolved_path,
            'errors': errors
        }

    except Exception as e:
        raise FilesystemError(server_error("Path resolution failed"))


def validate_status_transition(from_status: str, to_status: str) -> Dict[str, Any]:
    """Validate whether a task status transition is allowed"""
    allowed_transitions = {
        'backlog': ['in_progress'],
        'in_progress': ['review', 'backlog'],
        'review': ['done', 'in_progress'],
        'done': ['backlog']
    }

    if from_status == to_status:
        return {'valid': True}

    if from_status not in allowed_transitions:
        return {
            'valid': False,
            'error_message': f"Invalid source status: {from_status}"
        }

    if to_status not in allowed_transitions[from_status]:
        return {
            'valid': False,
            'error_message': f"Cannot transition from {from_status} to {to_status}"
        }

    return {'valid': True}


def get_allowed_transitions(status: str) -> List[str]:
    """Get allowed transitions for a status"""
    transitions = {
        'backlog': ['in_progress'],
        'in_progress': ['review', 'backlog'],
        'review': ['done', 'in_progress'],
        'done': ['backlog']
    }
    return transitions.get(status, [])


# ============================================================================
# COST TRACKING
# ============================================================================

def get_project_cost_summary(
    project_id: int,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve cost breakdown for a project over optional time period"""
    validate_id(project_id, "project")

    try:
        # Validate project exists
        get_project(project_id)

        # Validate date range
        if period_start and period_end:
            start_dt = datetime.fromisoformat(period_start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(period_end.replace('Z', '+00:00'))
            if end_dt < start_dt:
                raise ValidationError(bad_request("period_end must be >= period_start"))

        # In a real implementation, this would query agent activity logs
        # For now, return stub data
        db = get_db_connection()
        cursor = db.execute("SELECT COUNT(*) as count FROM tasks WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        task_count = row[0] if row else 0
        cursor.close()

        return {
            'project_id': project_id,
            'total_cost_usd': 0.0,
            'total_tokens': 0,
            'task_count': task_count,
            'period_start': period_start,
            'period_end': period_end
        }

    except (NotFoundError, ValidationError):
        raise
    except Exception as e:
        raise DatabaseError(server_error("Database query failed"))


# ============================================================================
# SSE EVENT PUBLISHING
# ============================================================================

def get_sse_bus():
    """Get SSE event bus (stub for testing)"""
    return None


def publish_task_event(event: Dict[str, Any]) -> bool:
    """Publish a task-related event to SSE bus with heartbeat support"""
    try:
        # Validate event can be serialized
        json_str = json.dumps(event)

        # Publish to bus if available
        bus = get_sse_bus()
        if bus:
            bus.publish(event)

        return True

    except (TypeError, ValueError) as e:
        raise InternalError({
            'error': 'serialization_error',
            'message': 'Event cannot be serialized to JSON',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        raise InternalError({
            'error': 'bus_error',
            'message': 'SSE bus is unavailable',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
