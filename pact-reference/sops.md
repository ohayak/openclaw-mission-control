# Operating Procedures

## Tech Stack
- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript 5 (strict mode)
- **UI:** React 19 + Tailwind CSS v4 + shadcn/ui components
- **Database:** SQLite via better-sqlite3 (synchronous, no ORM — raw SQL with typed wrappers)
- **Real-time:** Server-Sent Events (SSE) via Next.js Route Handlers
- **File Watching:** chokidar for filesystem monitoring
- **Charts:** recharts for cost/token visualizations
- **Testing:** Vitest for unit tests, Playwright for e2e
- **Package Manager:** pnpm

## Standards
- Type annotations on all exports and function signatures
- Prefer server components by default; use `"use client"` only when needed (interactivity, hooks)
- API routes in `app/api/` — return typed JSON responses
- Keep files under 250 lines; split into modules when approaching limit
- Use Zod for all external input validation (API params, file parsing)
- Error boundaries at page level; toast notifications for user-facing errors
- No `any` types — use `unknown` + type narrowing when type is uncertain

## Architecture Principles
- **Read from filesystem, write to SQLite.** Agent data, session data, PACT state = read from OpenClaw/PACT directories. Dashboard-specific data (user tasks, preferences, layout) = SQLite.
- **Polling + file watching, not direct integration.** Don't import OpenClaw or PACT as libraries. Read their files and call their CLIs. This keeps the dashboard decoupled and survivable if either changes.
- **SSE for push, not WebSocket.** One SSE endpoint that multiplexes event types. Clients subscribe with optional filters.
- **Convention: all data access through a `lib/data/` layer.** Components never read files or query SQLite directly.

## File Structure Convention
```
app/                    # Next.js App Router pages + API routes
  (dashboard)/          # Dashboard layout group
    page.tsx            # Home / overview
    projects/           # Project pages
    agents/             # Agent pages
    activity/           # Activity feed
    costs/              # Cost tracking
  api/                  # API route handlers
    events/             # SSE endpoint
    projects/           # Project CRUD
    tasks/              # Task CRUD
    agents/             # Agent data
    pact/               # PACT integration
components/             # React components
  ui/                   # shadcn/ui primitives
  dashboard/            # Dashboard-specific components
  pact/                 # PACT visualization components
lib/
  data/                 # Data access layer (filesystem + SQLite)
  pact/                 # PACT CLI wrapper + file parser
  openclaw/             # OpenClaw config/session reader
  db/                   # SQLite schema + queries
  sse/                  # SSE event bus
  types/                # Shared TypeScript types
```

## Verification
- All data access functions must have unit tests with fixture data
- API routes must have integration tests
- PACT file parsers must handle missing/malformed files gracefully (never crash on bad data)
- SSE endpoint must have a connection test
- No test may require a running OpenClaw instance or PACT daemon

## Preferences
- Prefer `fetch` over axios
- Prefer native `fs/promises` over third-party file utilities
- Prefer CSS variables + Tailwind over inline styles
- Prefer small, focused components over large monoliths
- Dark mode by default (agents work at night too)
