import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# User / Auth (keep existing)
# ---------------------------------------------------------------------------

class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# ---------------------------------------------------------------------------
# Item (keep existing)
# ---------------------------------------------------------------------------

class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class ItemCreate(ItemBase):
    pass


class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

class Message(SQLModel):
    message: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Mission Control Domain Models
# ---------------------------------------------------------------------------

class ProjectStatus(str, Enum):
    active = "active"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class TaskStatus(str, Enum):
    backlog = "backlog"
    in_progress = "in_progress"
    review = "review"
    done = "done"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class ProjectBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2048)
    status: ProjectStatus = Field(default=ProjectStatus.active)
    pact_dir: str | None = Field(default=None, max_length=1024)  # filesystem path to PACT project dir


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2048)
    status: ProjectStatus | None = None
    pact_dir: str | None = Field(default=None, max_length=1024)


class Project(ProjectBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    tasks: list["Task"] = Relationship(back_populates="project", cascade_delete=True)


class ProjectPublic(ProjectBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProjectsPublic(SQLModel):
    data: list[ProjectPublic]
    count: int


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class TaskBase(SQLModel):
    title: str = Field(min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=4096)
    status: TaskStatus = Field(default=TaskStatus.backlog)
    priority: TaskPriority = Field(default=TaskPriority.medium)
    assigned_agent_id: str | None = Field(default=None, max_length=64)  # openclaw agent id
    pact_component_id: str | None = Field(default=None, max_length=255)  # optional PACT component ref


class TaskCreate(TaskBase):
    project_id: uuid.UUID


class TaskUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=4096)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assigned_agent_id: str | None = None
    pact_component_id: str | None = None


class Task(TaskBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="project.id", nullable=False, ondelete="CASCADE")
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    project: Project | None = Relationship(back_populates="tasks")


class TaskPublic(TaskBase):
    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TasksPublic(SQLModel):
    data: list[TaskPublic]
    count: int


# ---------------------------------------------------------------------------
# Pydantic-only models (no DB table — data comes from filesystem)
# ---------------------------------------------------------------------------

class AgentIdentity(SQLModel):
    name: str
    emoji: str | None = None
    avatar: str | None = None
    theme: str | None = None


class AgentInfo(SQLModel):
    id: str
    name: str
    workspace: str | None = None
    model: str | None = None
    identity: AgentIdentity | None = None
    is_active: bool = False
    active_session_count: int = 0
    total_sessions: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0


class SessionInfo(SQLModel):
    id: str
    agent_id: str
    filename: str
    is_active: bool
    started_at: str | None = None
    cwd: str | None = None
    message_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str | None = None


class PactPhase(str, Enum):
    interview = "interview"
    shape = "shape"
    decompose = "decompose"
    contract = "contract"
    test = "test"
    implement = "implement"
    integrate = "integrate"
    polish = "polish"
    complete = "complete"
    unknown = "unknown"


class PactStatus(SQLModel):
    project_id: str
    phase: str
    status: str
    has_decomposition: bool = False
    has_contracts: bool = False
    component_count: int = 0
    components_contracted: int = 0
    components_tested: int = 0
    components_implemented: int = 0


class PactComponent(SQLModel):
    id: str
    name: str
    description: str | None = None
    layer: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    has_contract: bool = False
    has_tests: bool = False
    has_implementation: bool = False
    test_passed: int | None = None
    test_failed: int | None = None
    test_total: int | None = None


class PactHealth(SQLModel):
    project_id: str
    raw_output: str


class ActivityEvent(SQLModel):
    id: str
    event_type: str  # "session_start", "session_end", "task_update", "pact_phase", "agent_active"
    agent_id: str | None = None
    project_id: str | None = None
    message: str
    timestamp: str
    metadata: dict | None = None


class CostByAgent(SQLModel):
    agent_id: str
    agent_name: str
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    session_count: int


class CostByProject(SQLModel):
    project_id: str
    project_name: str
    assigned_agent_ids: list[str]
    total_tokens: int  # sum across assigned agents (approximated)


class MemoryFile(SQLModel):
    path: str  # relative path within project dir
    filename: str
    content: str
    last_modified: str | None = None


class MemoryFileUpdate(SQLModel):
    content: str
