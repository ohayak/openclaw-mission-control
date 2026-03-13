from fastapi import APIRouter

from app.api.routes import (
    activity,
    agents,
    costs,
    items,
    login,
    memory,
    pact,
    private,
    projects,
    tasks,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(agents.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(pact.router)
api_router.include_router(activity.router)
api_router.include_router(costs.router)
api_router.include_router(memory.router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
