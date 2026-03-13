"""
Agents API — reads from openclaw.json + session files.
No DB table; all data from filesystem.
"""
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser
from app.models import AgentInfo, SessionInfo
from app.services.openclaw_reader import (
    get_agent_by_id,
    get_all_agents,
    get_sessions_for_agent,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=list[AgentInfo])
def list_agents(current_user: CurrentUser) -> Any:
    """List all OpenClaw agents with status and token usage."""
    return get_all_agents()


@router.get("/{agent_id}", response_model=AgentInfo)
def get_agent(agent_id: str, current_user: CurrentUser) -> Any:
    """Get a single agent by ID."""
    agent = get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/{agent_id}/sessions", response_model=list[SessionInfo])
def get_agent_sessions(agent_id: str, current_user: CurrentUser) -> Any:
    """Get all sessions for an agent."""
    agent = get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return get_sessions_for_agent(agent_id)
