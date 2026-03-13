# OpenClaw Mission Control

Self-hosted dashboard for managing OpenClaw AI agent teams.

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)

## Features

- **Agent Dashboard** — View all OpenClaw agents, their status, active sessions, and token usage
- **Project Management** — Create and track projects with Kanban task boards
- **PACT Pipeline** — Visualize PACT contract-first pipeline stages per project
- **Activity Feed** — Real-time event stream via SSE
- **Cost Tracking** — Per-project and per-agent token usage charts
- **Shared Project Memory** — Per-project knowledge base (decisions, patterns, gotchas) that agents can load for context
- **Dark Mode** — Default dark theme, responsive design

## Stack

- **Backend:** FastAPI + SQLModel + PostgreSQL + Alembic + JWT auth
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- **Real-time:** Server-Sent Events (SSE) + watchdog file monitoring
- **Infra:** Docker Compose, Traefik

## Quick Start

```bash
git clone https://github.com/ohayak/openclaw-mission-control.git
cd openclaw-mission-control
cp .env.example .env  # Edit with your settings
docker compose up -d
```

Dashboard: http://localhost:5173
API docs: http://localhost:8000/docs

## Configuration

Key environment variables in `.env`:

| Variable | Description | Default |
|---|---|---|
| `OPENCLAW_CONFIG_PATH` | Path to openclaw.json | `/data/.openclaw/openclaw.json` |
| `OPENCLAW_AGENTS_DIR` | Path to agent session data | `/data/.openclaw/agents` |
| `PACT_PROJECTS_DIR` | Root directory for PACT projects | `/data/.openclaw/workspace` |
| `SECRET_KEY` | JWT secret key | (generate one) |
| `FIRST_SUPERUSER` | Admin email | `admin@example.com` |
| `FIRST_SUPERUSER_PASSWORD` | Admin password | (set one) |

## Architecture

```
backend/
  app/
    api/routes/     # FastAPI route handlers
      agents.py     # Agent discovery from openclaw.json
      projects.py   # Project CRUD
      tasks.py      # Task CRUD + Kanban
      pact.py       # PACT pipeline status
      activity.py   # Activity feed + SSE
      costs.py      # Token/cost analytics
      memory.py     # Project shared memory
    services/       # Business logic
      openclaw_reader.py  # Reads openclaw.json + session JSONL
      pact_reader.py      # Reads PACT project directories
      event_bus.py        # In-memory pub/sub for SSE
      file_watcher.py     # Watchdog-based file monitoring
    models.py       # SQLModel domain models
    core/           # Config, DB, auth
frontend/
  src/
    components/MissionControl/
      AgentCard.tsx
      KanbanBoard.tsx       # @dnd-kit drag-and-drop
      PactPipeline.tsx
      PactComponentTree.tsx
      ActivityFeed.tsx
      CostChart.tsx         # recharts
      MemoryEditor.tsx      # Markdown editor
    routes/_layout/
      index.tsx             # Dashboard overview
      agents.tsx            # Agent list
      projects.tsx          # Project list
      activity.tsx          # Activity feed
      costs.tsx             # Cost analytics
```

## How It Reads OpenClaw Data

The dashboard reads directly from the OpenClaw filesystem:

- **Agents**: Parsed from `openclaw.json` → `agents.list[]`
- **Sessions**: JSONL files at `agents/<id>/sessions/*.jsonl`
- **Agent Status**: `.jsonl.lock` file = agent is active
- **Token Usage**: Extracted from session message `usage` fields
- **PACT Status**: Read from `.pact/state.json`, `decomposition/tree.json`

No separate database for agent data — PostgreSQL is only for dashboard-specific state (projects, tasks, user accounts).

## Built With

This project was scaffolded using [PACT](https://github.com/jmcentire/pact) (contract-first multi-agent framework) and the [FastAPI full-stack template](https://github.com/fastapi/full-stack-fastapi-template).

## License

MIT
