"""
Costs API — token usage analytics parsed from session JSONL files.
"""
from typing import Any

from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import CostByAgent, CostByProject, Project
from app.services.openclaw_reader import get_token_usage_by_agent, get_all_agents

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("/by-agent", response_model=list[CostByAgent])
def costs_by_agent(current_user: CurrentUser) -> Any:
    """Token usage broken down by agent."""
    usage = get_token_usage_by_agent()
    return [
        CostByAgent(
            agent_id=v["agent_id"],
            agent_name=v["agent_name"],
            total_input_tokens=v["total_input_tokens"],
            total_output_tokens=v["total_output_tokens"],
            total_tokens=v["total_tokens"],
            session_count=v["session_count"],
        )
        for v in usage.values()
    ]


@router.get("/by-project", response_model=list[CostByProject])
def costs_by_project(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Token usage broken down by project.
    Projects don't have direct token tracking — we approximate by
    listing projects and their assigned agent IDs from tasks.
    """
    from sqlmodel import col
    from app.models import Task

    projects = session.exec(select(Project)).all()
    usage = get_token_usage_by_agent()

    result = []
    for project in projects:
        # Get all agent IDs assigned to tasks in this project
        tasks = session.exec(
            select(Task.assigned_agent_id)
            .where(Task.project_id == project.id)
            .where(Task.assigned_agent_id.isnot(None))  # type: ignore
        ).all()
        assigned_agents = list({a for a in tasks if a})

        # Sum tokens across assigned agents (rough approximation)
        total_tokens = sum(
            usage.get(aid, {}).get("total_tokens", 0)
            for aid in assigned_agents
        )

        result.append(CostByProject(
            project_id=str(project.id),
            project_name=project.name,
            assigned_agent_ids=assigned_agents,
            total_tokens=total_tokens,
        ))

    return result
