"""
Tasks API — CRUD with Kanban status, backed by PostgreSQL.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    Project,
    Task,
    TaskCreate,
    TaskPublic,
    TasksPublic,
    TaskStatus,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=TasksPublic)
def list_tasks(
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID | None = None,
    status: TaskStatus | None = None,
    assigned_agent_id: str | None = None,
    skip: int = 0,
    limit: int = 200,
) -> Any:
    query = select(Task)
    if project_id:
        query = query.where(Task.project_id == project_id)
    if status:
        query = query.where(Task.status == status)
    if assigned_agent_id:
        query = query.where(Task.assigned_agent_id == assigned_agent_id)
    query = query.order_by(col(Task.updated_at).desc()).offset(skip).limit(limit)
    tasks = session.exec(query).all()
    return TasksPublic(data=list(tasks), count=len(tasks))


@router.get("/{task_id}", response_model=TaskPublic)
def get_task(
    task_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/", response_model=TaskPublic)
def create_task(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_in: TaskCreate,
) -> Any:
    # Verify project exists
    project = session.get(Project, task_in.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = Task.model_validate(task_in)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskPublic)
def update_task(
    *,
    task_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    task_in: TaskUpdate,
) -> Any:
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    update_data = task_in.model_dump(exclude_unset=True)
    task.sqlmodel_update(update_data)
    task.updated_at = datetime.now(timezone.utc)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}", response_model=Message)
def delete_task(
    task_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(task)
    session.commit()
    return Message(message="Task deleted successfully")
