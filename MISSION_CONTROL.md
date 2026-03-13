# OpenClaw Mission Control

A self-hosted dashboard for managing your OpenClaw AI agent team.

## What It Does

- **Agent Overview** — Live status, session count, token usage for all OpenClaw agents
- **Project Management** — Create/track projects with Kanban task board
- **PACT Pipeline** — Visualize PACT pipeline stages and component tree for PACT-managed projects
- **Activity Feed** — Real-time event stream with live polling (5s)
- **Cost Tracking** — Token usage analytics by agent and project
- **Project Memory** — View/edit shared project memory files (CONTEXT.md, decisions.md, etc.)

## Architecture

| Layer | Tech |
|-------|------|
| Backend API | FastAPI + SQLModel + PostgreSQL |
| Auth | JWT (existing template) |
| Frontend | React 19 + TypeScript + Vite + Tailwind + shadcn/ui |
| Drag-and-drop | @dnd-kit/core |
| Charts | recharts |
| File watching | watchdog (Python) |
| Realtime | HTTP polling (every 5s) with SSE endpoint at `/api/v1/activity/stream` |

## Quick Start

### Local Development

```bash
# 1. Copy and configure .env
cp .env .env.local
# Edit SECRET_KEY, POSTGRES_PASSWORD, FIRST_SUPERUSER_PASSWORD

# 2. Start with Docker Compose
docker compose watch

# Backend:  http://localhost:8000
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/api/v1/docs
```

### Prerequisites

- Docker + Docker Compose
- `/data/.openclaw/` directory accessible (mounted via volumes)

## New API Endpoints

All endpoints require JWT auth (same as existing `/api/v1/login/access-token`).

### Agents (read-only, from filesystem)
```
GET /api/v1/agents/                   — list all agents
GET /api/v1/agents/{id}               — single agent
GET /api/v1/agents/{id}/sessions      — session list with token stats
```

### Projects (PostgreSQL)
```
GET    /api/v1/projects/              — list projects
POST   /api/v1/projects/              — create project
GET    /api/v1/projects/{id}          — get project
PATCH  /api/v1/projects/{id}          — update project
DELETE /api/v1/projects/{id}          — delete project
```

### Tasks (PostgreSQL, Kanban)
```
GET    /api/v1/tasks/?project_id=...  — list tasks (filterable)
POST   /api/v1/tasks/                 — create task
GET    /api/v1/tasks/{id}             — get task
PATCH  /api/v1/tasks/{id}             — update task (status, assignment, etc.)
DELETE /api/v1/tasks/{id}             — delete task
```

### PACT (read-only, from filesystem)
```
GET /api/v1/pact/{project_id}/status       — pipeline phase + component counts
GET /api/v1/pact/{project_id}/components   — component list with contract/test/impl status
GET /api/v1/pact/{project_id}/health       — runs `pact health .` and returns output
```

### Activity
```
GET /api/v1/activity/          — recent events (last N)
GET /api/v1/activity/stream    — SSE stream (requires Bearer token in header)
```

### Costs
```
GET /api/v1/costs/by-agent     — token usage per agent
GET /api/v1/costs/by-project   — token usage per project
```

### Memory
```
GET /api/v1/memory/{project_id}/files              — list all memory files
GET /api/v1/memory/{project_id}/files/{filename}   — read file
PUT /api/v1/memory/{project_id}/files/{filename}   — write file
DELETE /api/v1/memory/{project_id}/files/{filename} — delete file
GET /api/v1/memory/{project_id}/context?maxTokens=8000 — compiled context doc
```

## Environment Variables

Add to `.env`:

```env
OPENCLAW_CONFIG_PATH=/data/.openclaw/openclaw.json
OPENCLAW_AGENTS_DIR=/data/.openclaw/agents
PACT_PROJECTS_DIR=/data/.openclaw/workspace
```

## Database Migration

After first deploy:
```bash
# Run migrations (included in prestart.sh automatically)
docker compose exec backend alembic upgrade head
```

The migration `a1b2c3d4e5f6` adds `project` and `task` tables.

## Routes

| Path | Description |
|------|-------------|
| `/` | Dashboard overview |
| `/agents` | Agent list + token stats |
| `/agents/:id` | Agent detail + sessions |
| `/projects` | Project list + create |
| `/projects/:id` | Project detail + Kanban board |
| `/projects/:id/memory` | Project memory editor |
| `/activity` | Live activity feed |
| `/costs` | Token/cost charts |
| `/settings` | User settings |
| `/admin` | Admin panel (superusers only) |

## Project Memory

Each project can have a set of shared markdown files that agents load before starting work:

- `CONTEXT.md` — high-level project overview (auto-loaded by agents)
- `memory/decisions.md` — architectural decisions
- `memory/patterns.md` — code conventions
- `memory/gotchas.md` — known issues
- `memory/glossary.md` — terminology

Files are stored on the filesystem at the project's `pact_dir` (if set) or `workspace/<project-slug>/`.

Agents can load compiled context via: `GET /api/v1/memory/{project_id}/context?maxTokens=8000`

## PACT Integration

To enable PACT pipeline visualization for a project:
1. Set `pact_dir` to the absolute filesystem path of the PACT project
2. The dashboard reads `.pact/state.json`, `decomposition/decomposition.json`, etc. directly
3. The PACT tab appears automatically on the project detail page
