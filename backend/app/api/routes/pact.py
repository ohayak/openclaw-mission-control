"""
PACT API — reads PACT project directories and spawns PACT CLI subprocesses.
"""
import uuid
from pathlib import Path
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from app.api.deps import CurrentUser, SessionDep, get_db
from app.core import security
from app.core.config import settings
from app.models import PactComponent, PactHealth, PactStatus, Project, TokenPayload, User
from app.services.pact_executor import (
    get_logs,
    is_running,
    spawn_pact,
    stream_logs,
)
from app.services.pact_reader import get_pact_components, get_pact_health, get_pact_status

router = APIRouter(prefix="/pact", tags=["pact"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class PactRunRequest(BaseModel):
    phase: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_project_dir(project_id: uuid.UUID, session: SessionDep) -> str:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.pact_dir:
        raise HTTPException(status_code=400, detail="Project has no PACT directory configured")
    return project.pact_dir


def _get_user_from_token(token: str, session: Session) -> User:
    """Validate a JWT token string and return the associated user.

    Used for endpoints that accept the token as a query param (e.g. SSE streams
    where EventSource doesn't support custom Authorization headers).
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


# ---------------------------------------------------------------------------
# Read endpoints (existing)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Action endpoints (new)
# ---------------------------------------------------------------------------


def _get_project_model_override(project_id: uuid.UUID, session: SessionDep) -> str | None:
    """Return the model_override for a project, or None if not set."""
    project = session.get(Project, project_id)
    return getattr(project, "model_override", None) if project else None


@router.post("/{project_id}/init", status_code=202)
def pact_init(
    project_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    """Spawn `pact init .` in the project directory."""
    pact_dir = _get_project_dir(project_id, session)
    model_override = _get_project_model_override(project_id, session)
    try:
        spawn_pact(str(project_id), pact_dir, ["init", "."], model_override=model_override)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"status": "started"}


@router.post("/{project_id}/interview/start", status_code=202)
def pact_interview_start(
    project_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    """Spawn `pact run interview .` in the project directory."""
    pact_dir = _get_project_dir(project_id, session)
    model_override = _get_project_model_override(project_id, session)
    try:
        spawn_pact(str(project_id), pact_dir, ["run", "interview", "."], model_override=model_override)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"status": "started"}


@router.post("/{project_id}/run", status_code=202)
def pact_run(
    project_id: uuid.UUID,
    body: PactRunRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    """Spawn `pact run [phase] .` in the project directory."""
    pact_dir = _get_project_dir(project_id, session)
    model_override = _get_project_model_override(project_id, session)
    args = ["run"] + ([body.phase] if body.phase else []) + ["."]
    try:
        spawn_pact(str(project_id), pact_dir, args, model_override=model_override)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"status": "started"}


@router.get("/{project_id}/stream")
def pact_stream(
    project_id: uuid.UUID,
    session: SessionDep,
    # Accept token as query param for SSE (EventSource doesn't support headers)
    # Standard Authorization header is also accepted via current_user fallback
    token: Annotated[str | None, Query()] = None,
    current_user: CurrentUser | None = None,
) -> StreamingResponse:
    """
    SSE stream of PACT log output.
    Tails the log file while the process runs, then sends a 'done' event.
    If no log file exists (spawn failed), sends an error SSE event.

    Auth: accepts Bearer token in Authorization header OR ?token=... query param
    (EventSource API in browsers does not support custom headers).
    """
    # Resolve auth: header token (current_user) or query param token
    if current_user is None:
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Authentication required",
            )
        _get_user_from_token(token, session)

    _get_project_dir(project_id, session)  # project existence check
    pid_str = str(project_id)

    def event_generator():
        from app.services.pact_executor import _log_path

        # If there's no log file and no process running, report the failure
        if not _log_path(pid_str).exists() and not is_running(pid_str):
            yield "event: error\ndata: No log output found. The PACT process may have failed to start.\n\n"
            return

        try:
            for line in stream_logs(pid_str):
                yield f"data: {line}\n\n"
        except GeneratorExit:
            # Client disconnected — stop iterating gracefully
            return
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{project_id}/logs")
def pact_logs(
    project_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    """Return full historical log content for a project."""
    _get_project_dir(project_id, session)  # auth + existence check
    return {"logs": get_logs(str(project_id))}


# ---------------------------------------------------------------------------
# Component detail endpoints (Phase 5)
# ---------------------------------------------------------------------------


@router.get("/{project_id}/components/{component_id}/contract")
def pact_component_contract(
    project_id: uuid.UUID,
    component_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    """Return the contract file content for a specific component."""
    pact_dir = _get_project_dir(project_id, session)
    p = Path(pact_dir)
    for fname in ["interface.json", "interface.py"]:
        contract_file = p / "contracts" / component_id / fname
        if contract_file.exists():
            return {"filename": fname, "content": contract_file.read_text()}
    raise HTTPException(status_code=404, detail="Contract not found")


@router.get("/{project_id}/components/{component_id}/tests")
def pact_component_tests(
    project_id: uuid.UUID,
    component_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    """Return test file content for a specific component."""
    pact_dir = _get_project_dir(project_id, session)
    test_dir = Path(pact_dir) / "tests" / component_id
    if not test_dir.exists():
        return {"files": []}
    files = []
    for f in sorted(test_dir.iterdir()):
        if f.is_file():
            files.append({"filename": f.name, "content": f.read_text()})
    return {"files": files}


@router.post("/{project_id}/components/{component_id}/retest", status_code=202)
def pact_component_retest(
    project_id: uuid.UUID,
    component_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    """Spawn `pact test <component_id> .` to retest a single component."""
    pact_dir = _get_project_dir(project_id, session)
    model_override = _get_project_model_override(project_id, session)
    try:
        spawn_pact(str(project_id), pact_dir, ["test", component_id, "."], model_override=model_override)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"status": "started"}
