# Task: OpenClaw Mission Control

Build a self-hosted mission control dashboard for managing an OpenClaw AI agent team's work and projects.

## What It Does

A Next.js web application that serves as the central command center for an OpenClaw deployment. It provides:

1. **Project Management** — Create, track, and manage projects with tasks. Each project can optionally use PACT (contract-first multi-agent framework) for decomposition and implementation.

2. **Agent Overview** — Show all OpenClaw agents (discovered from `openclaw.json`), their current status, active sessions, token usage, and which projects/tasks they're assigned to.

3. **PACT Pipeline Visualization** — For PACT-managed projects, show the full pipeline: Interview → Shape → Decompose → Contract → Test → Implement → Integrate → Polish. Visualize the component tree, contract status, test pass/fail, and implementation progress per component.

4. **Task Board** — Kanban-style board (Backlog → In Progress → Review → Done) for both PACT-decomposed tasks and standalone tasks. Tasks can be assigned to agents or humans.

5. **Live Activity Feed** — Real-time stream of events: agent actions, PACT pipeline transitions, task status changes, session starts/stops, errors.

6. **Cost & Token Tracking** — Per-project and per-agent cost analytics. Token usage over time. Budget alerts.

7. **PACT Health Dashboard** — Surface PACT's health metrics: output/planning ratio, rejection rate, budget velocity, phase balance, cascade detection.

8. **Shared Project Memory** — Each project gets a shared knowledge base that any agent can load before working on it. This bridges the gap between team-wide shared memory (`/data/.openclaw/shared/`) and individual agent memory (`MEMORY.md`). Features:
   - **CONTEXT.md** — Auto-maintained high-level project context file (architecture overview, current state, key decisions). Agents load this before starting any project work.
   - **Memory files** — Structured knowledge per project: `decisions.md` (architectural decisions with rationale and date), `patterns.md` (code patterns/conventions), `gotchas.md` (known issues/workarounds), `glossary.md` (project-specific terminology).
   - **History summaries** — Automatic summarization of agent work sessions into weekly/sprint digests, stored in `history/`.
   - **Dashboard UI** — View, edit, search, and manage all project memory files from the dashboard. Markdown editor with preview.
   - **PACT integration** — For PACT-managed projects, automatically incorporate PACT's `learnings/`, `decomposition/decisions.json`, and `sops.md` into the shared context. The CONTEXT.md can reference or inline PACT artifacts.
   - **Agent loading protocol** — A standardized way for agents to load project context: `GET /api/projects/:id/context` returns a compiled markdown document with all relevant project memory, sized to fit within a context window budget (configurable, default 8K tokens). Agents call this endpoint (or read the file directly) before starting work.

## Context

- **OpenClaw** is an AI agent orchestration platform. It manages multiple AI agents (each with their own workspace, personality, and capabilities) via a Gateway process. Configuration lives in `openclaw.json`.
- **PACT** (`pact-agents` on PyPI) is a contract-first multi-agent engineering framework. It decomposes tasks into components, generates typed interface contracts and executable tests, then dispatches implementation to agents. Projects live as directories with `task.md`, `sops.md`, `pact.yaml`, `decomposition/`, `contracts/`, `src/`, `tests/`.
- The dashboard reads from the OpenClaw filesystem (openclaw.json, workspaces, session data) and PACT project directories. No separate database required for agent/session data — SQLite only for dashboard-specific state (user preferences, dashboard tasks not managed by PACT).
- Authentication: simple password auth with secure cookie (single-user/small-team use case).

## Key Constraints

- Must run alongside OpenClaw on the same host (reads filesystem directly)
- SQLite for any dashboard-specific persistence (no Postgres/Redis)
- Server-Sent Events (SSE) for real-time updates (simpler than WebSocket for this use case)
- File-watching for PACT project directories (detect pipeline state changes)
- Responsive design (usable on mobile for checking status on the go)
- The dashboard should be readable and modifiable by AI agents (clean code, clear structure)

## Non-Goals (for v1)

- Multi-user role-based access (v1 is single password auth)
- Direct agent command execution from the dashboard (v1 is read + task management, not a terminal)
- Git integration (not in v1)
- Webhook/external notification support (not in v1)

## Success Criteria

- Can view all OpenClaw agents and their current state
- Can create projects and tasks, assign them to agents
- Can view PACT pipeline status for any PACT-managed project
- Can see real-time activity feed updating via SSE
- Can view cost/token breakdown per project and per agent
- Dashboard loads in under 2 seconds on localhost
- Works on Chrome, Firefox, Safari (desktop + mobile)
