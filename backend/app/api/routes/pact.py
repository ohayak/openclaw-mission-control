"""
PACT API — reads PACT project directories.
"""
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import PactComponent, PactHealth, PactStatus, Project
from app.services.pact_reader import get_pact_components, get_pact_health, get_pact_status

router = APIRouter(prefix="/pact", tags=["pact"])


def _get_project_dir(project_id: uuid.UUID, session: SessionDep) -> str:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.pact_dir:
        raise HTTPException(status_code=400, detail="Project has no PACT directory configured")
    return project.pact_dir


@router.get("/{project_id}/status", response_model=PactStatus)
def pact_status(
    project_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    pact_dir = _get_project_dir(project_id, session)
    return get_pact_status(pact_dir)


@router.get("/{project_id}/components", response_model=list[PactComponent])
def pact_components(
    project_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    pact_dir = _get_project_dir(project_id, session)
    return get_pact_components(pact_dir)


@router.get("/{project_id}/health", response_model=PactHealth)
def pact_health(
    project_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    pact_dir = _get_project_dir(project_id, session)
    return get_pact_health(pact_dir)
