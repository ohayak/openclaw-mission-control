"""
Memory API — CRUD for project memory files (CONTEXT.md, decisions.md, etc.)
Files are read/written directly to the filesystem in the project directory.
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import MemoryFile, MemoryFileUpdate, Message, Project

router = APIRouter(prefix="/memory", tags=["memory"])

# Allowed memory file names (whitelist for security)
ALLOWED_MEMORY_FILES = {
    "CONTEXT.md",
    "decisions.md",
    "patterns.md",
    "gotchas.md",
    "glossary.md",
}

MEMORY_SUBDIR = "memory"


def _get_project_base_dir(project_id: uuid.UUID, session: SessionDep) -> Path:
    """Get the base directory for a project — uses pact_dir if set, else workspace/<name>."""
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.core.config import settings
    if project.pact_dir:
        return Path(project.pact_dir)
    # Fall back to workspace dir based on project name (slugified)
    slug = project.name.lower().replace(" ", "-").replace("/", "-")
    return Path(settings.PACT_PROJECTS_DIR) / slug


def _safe_path(base: Path, filename: str) -> Path:
    """Return safe path within base dir, raising 400 if file not allowed."""
    # Allow CONTEXT.md at base level, others in memory/ subdir
    if filename == "CONTEXT.md":
        return base / filename
    if filename in ALLOWED_MEMORY_FILES:
        return base / MEMORY_SUBDIR / filename
    raise HTTPException(status_code=400, detail=f"File '{filename}' not in allowed list")


@router.get("/{project_id}/files", response_model=list[MemoryFile])
def list_memory_files(
    project_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    base = _get_project_base_dir(project_id, session)
    files: list[MemoryFile] = []

    for filename in ALLOWED_MEMORY_FILES:
        path = _safe_path(base, filename)
        if path.exists():
            try:
                content = path.read_text(errors="replace")
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
                relative = str(path.relative_to(base))
                files.append(MemoryFile(
                    path=relative,
                    filename=filename,
                    content=content,
                    last_modified=mtime,
                ))
            except Exception:
                pass

    return files


@router.get("/{project_id}/files/{filename}", response_model=MemoryFile)
def get_memory_file(
    project_id: uuid.UUID,
    filename: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    base = _get_project_base_dir(project_id, session)
    path = _safe_path(base, filename)

    if not path.exists():
        # Return empty file — creates it on first save
        relative = filename if filename == "CONTEXT.md" else f"{MEMORY_SUBDIR}/{filename}"
        return MemoryFile(path=relative, filename=filename, content="", last_modified=None)

    content = path.read_text(errors="replace")
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    relative = str(path.relative_to(base))
    return MemoryFile(path=relative, filename=filename, content=content, last_modified=mtime)


@router.put("/{project_id}/files/{filename}", response_model=MemoryFile)
def update_memory_file(
    project_id: uuid.UUID,
    filename: str,
    update: MemoryFileUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    base = _get_project_base_dir(project_id, session)
    path = _safe_path(base, filename)

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(update.content)

    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    relative = str(path.relative_to(base))
    return MemoryFile(path=relative, filename=filename, content=update.content, last_modified=mtime)


@router.delete("/{project_id}/files/{filename}", response_model=Message)
def delete_memory_file(
    project_id: uuid.UUID,
    filename: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    base = _get_project_base_dir(project_id, session)
    path = _safe_path(base, filename)

    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    path.unlink()
    return Message(message=f"{filename} deleted")


@router.get("/{project_id}/context", response_model=MemoryFile)
def get_compiled_context(
    project_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    max_tokens: int = 8000,
) -> Any:
    """
    Returns a compiled context document with all project memory,
    trimmed to approximately max_tokens (roughly 4 chars/token).
    """
    base = _get_project_base_dir(project_id, session)
    max_chars = max_tokens * 4

    parts: list[str] = []

    # CONTEXT.md first
    ctx_path = base / "CONTEXT.md"
    if ctx_path.exists():
        parts.append(f"# Project Context\n\n{ctx_path.read_text(errors='replace')}\n")

    # Then other memory files
    for filename in ["decisions.md", "patterns.md", "gotchas.md", "glossary.md"]:
        path = base / MEMORY_SUBDIR / filename
        if path.exists():
            content = path.read_text(errors="replace")
            parts.append(f"---\n## {filename}\n\n{content}\n")

    combined = "\n".join(parts)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n[Context truncated to fit token budget]"

    return MemoryFile(
        path="CONTEXT.md",
        filename="CONTEXT.md",
        content=combined or "# No context available yet\n\nCreate memory files to build project context.",
        last_modified=None,
    )
