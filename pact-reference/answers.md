# Interview Answers

## Q1: openclaw.json schema + session data structure

openclaw.json lives at `/data/.openclaw/openclaw.json`. Key structure:

```json
{
  "agents": {
    "list": [
      {
        "id": "main",
        "name": "Jim Halpert",
        "identity": { "name": "Jim Halpert", "emoji": "😏", "avatar": "avatars/jim.jpg" },
        "subagents": { "allowAgents": ["possum", "pam", "mike", "kelly"] },
        "tools": { "profile": "full" }
        // no "workspace" key = uses default /data/.openclaw/workspace
      },
      {
        "id": "possum",
        "name": "Dwight Schrute",
        "workspace": "/data/.openclaw/workspace-possum",
        "model": "cliproxy/claude-sonnet-4-6",
        "identity": { "name": "Dwight Schrute", "theme": "AI Specialist", "emoji": "🦝", "avatar": "avatars/dwight.jpg" },
        "subagents": { "allowAgents": ["main"] },
        "tools": { "profile": "full" }
      }
      // agents: main, possum (Dwight), pam, mike, kelly
    ],
    "defaults": { "model": { "primary": "cliproxy/claude-opus-4-6", ... } }
  },
  "models": { "providers": { ... } },
  "browser": { ... },
  "env": { ... }
}
```

**Session data** lives at `/data/.openclaw/agents/<agentId>/sessions/`.
- Active sessions tracked in `sessions.json` (map of session keys → metadata)
- Individual sessions are `.jsonl` files (UUID-named), one JSON object per line
- Session JSONL format:
  - Line 1: `{ "type": "session", "version": 3, "id": "...", "timestamp": "...", "cwd": "..." }`
  - Subsequent lines: `{ "type": "message", "id": "...", "timestamp": "...", "message": { "role": "user|assistant", "model": "claude-opus-4-6", "usage": { "input": 23153, "output": 184, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 23337, "cost": { "input": 0, "output": 0, "total": 0 } } } }`
- Cost values are 0 (proxy doesn't report cost) — use token counts + model pricing table instead
- `.jsonl.lock` = session currently active; `.jsonl.reset.*` = archived; `.jsonl.deleted.*` = soft-deleted
- Agent liveness: session has a `.jsonl.lock` file = agent is currently active

**Default workspace** for agent `main`: `/data/.openclaw/workspace`
**Other agent workspaces**: `/data/.openclaw/workspace-<agentId>` (e.g., workspace-possum)
**Memory SQLite**: `/data/.openclaw/memory/<agentId>.sqlite` (vector memory, not session data)

## Q2: PACT project directory structure

```
my-project/
  task.md              # Human-written task description
  sops.md              # Operating procedures / tech stack
  pact.yaml            # Budget, parallelism, model config
  design.md            # Auto-maintained by PACT
  design.json          # Structured design (auto)
  decomposition/
    interview.json     # Questions, assumptions, acceptance criteria
    answers.md         # Human answers to interview questions (THIS FILE format)
    decomposition.json # Component tree: { components: [{ id, name, description, dependencies, layer }] }
    pitch.md           # Shape Up pitch (if shaping enabled)
  contracts/<cid>/     # Per-component contracts
    contract.md        # Typed interface spec
    contract.json      # Structured contract
  src/<cid>/           # Per-component implementations
    *.ts / *.py        # Source files
  tests/<cid>/         # Per-component tests
    test_*.py / *.test.ts
    results.json       # { passed: N, failed: N, total: N, timestamp }
  learnings/           # Accumulated learnings from runs
  .pact/               # Ephemeral run state (gitignored)
    state.json         # { phase: "implement"|"contract"|"test"|..., status: "running"|"paused"|"complete" }
    audit.jsonl        # Full audit trail of all agent actions
    implementations/   # Per-attempt metadata
    monitoring/        # Incidents, budget state
```

**Pipeline stage detection** (from filesystem state):
- No decomposition/decomposition.json → Interview/Shape phase
- decomposition.json exists, no contracts/ subdirs → Decompose complete
- contracts/<cid>/contract.json exists → Contract phase done for that component
- tests/<cid>/results.json exists → Test phase done
- src/<cid>/ has files → Implement done
- .pact/state.json `phase` field is authoritative when daemon is running

**PACT CLI** (available commands):
`pact init`, `pact run`, `pact daemon`, `pact status`, `pact components`, `pact build <id>`,
`pact interview`, `pact answer`, `pact approve`, `pact validate`, `pact log`, `pact health`,
`pact stop`, `pact signal`, `pact watch`, `pact tree`, `pact cost`, `pact tasks`

Dashboard should: read PACT files directly for status display, invoke CLI only for actions
(approve, build, stop) — never import pact as a library.

## Q3: Token/cost data

Token data IS available in session JSONL files. Each assistant message has:
```json
"usage": { "input": 23153, "output": 184, "cacheRead": 22980, "cacheWrite": 0, "totalTokens": 23337 }
```
Cost values are all 0 (proxy doesn't report cost). Dashboard should calculate cost from
token counts × model pricing (from `pact pricing` output or hardcoded table).
This is NOT a prerequisite — read tokens from session files and compute cost client-side.

## Q4: Task assignment to agents

Dashboard-local label only (write to SQLite). Agents do NOT discover tasks from the dashboard.
The dashboard is a planning/tracking tool. If we want an agent to actually work on something,
that's a future feature (write to agent workspace file + notify via OpenClaw sessions_send).
V1: pure label/tracking.

## Q5: PACT CLI interface

Dashboard reads files directly for all status/display. Invokes CLI only for:
- `pact approve .` — approve interview and start pipeline
- `pact stop .` — stop running daemon
- `pact build . <component-id>` — rebuild a specific component
- `pact health .` — get health metrics JSON (parse stdout)
- `pact log . --json --tail 50` — get recent audit events

All CLI calls: spawn child process, capture stdout/stderr, parse output. Never `exec` in the
Next.js API route directly — wrap in a lib/pact/cli.ts module.

## Q6: PACT health metrics

Run `pact health <project-dir>` — it prints health metrics. Parse the output.
Also parseable from `.pact/audit.jsonl` for historical data:
- output/planning ratio: count output tokens vs planning-phase tokens from audit log
- rejection rate: count rejected vs accepted outputs in audit
- budget velocity: tokens spent per hour from audit timestamps
- Cascade detection: component failure counts from state.json

For V1: call `pact health .` and display the parsed output. No need to reimplement the math.

## Q7: Phased delivery

Yes — decompose into phases but implement all in one PACT run with parallel components:
- Core data layer (OpenClaw reader, PACT file parser, SQLite schema) — foundation
- API routes (projects, tasks, agents, PACT, SSE/events) — depend on data layer
- UI components (layout, agent cards, kanban, PACT pipeline viz, activity feed, cost charts)
- Auth + file watcher + SSE event bus — cross-cutting

These map naturally to parallel PACT components.

## Q8: Existing deployment to develop against

YES — full live deployment available:
- `/data/.openclaw/openclaw.json` — real config
- `/data/.openclaw/agents/main/sessions/` — real session JSONL files
- `/data/.openclaw/agents/<id>/sessions/` — per-agent sessions
- 5 agents: main (Jim), possum (Dwight), pam, mike, kelly
- PACT project will be at `/data/.openclaw/workspace/mission-control/`

Tests should use fixture copies of real files (anonymized/trimmed). No mocking needed for
file format — we have real examples.

## Q9: Kanban drag-and-drop

Desktop: drag-and-drop required (use @dnd-kit/core — lighter than react-beautiful-dnd, works with React 19).
Mobile: status dropdown/button (no drag on mobile). Detect via CSS/touch media queries.

## Q11: Shared Project Memory

Each project gets a `memory/` directory for shared context that all agents can load:

```
project-dir/
  CONTEXT.md              # Auto-maintained high-level summary (compiled from below)
  memory/
    decisions.md          # Architectural decisions with rationale + date
    patterns.md           # Code patterns and conventions used in this project
    gotchas.md            # Known issues, workarounds, sharp edges
    glossary.md           # Project-specific terminology
    history/
      2026-W10.md         # Weekly digest of agent work sessions
      2026-W11.md
```

**How it connects to existing OpenClaw memory hierarchy:**
- **Team-wide** shared context: `/data/.openclaw/shared/` (TEAM.md, PROJECTS.md, INFRA.md, DECISIONS.md) — read by ALL agents
- **Project-level** shared context: `project-dir/memory/` + `CONTEXT.md` — NEW, read by agents assigned to that project
- **Agent-level** personal context: each agent's `MEMORY.md` + `memory/YYYY-MM-DD.md` — private to that agent

**PACT integration:** For PACT-managed projects, the project memory auto-incorporates:
- `learnings/` directory entries → merged into patterns.md or gotchas.md
- `decomposition/decisions.json` → merged into decisions.md
- `sops.md` → referenced in CONTEXT.md

**Agent loading protocol:**
- API endpoint: `GET /api/projects/:id/context?maxTokens=8000`
- Returns compiled markdown with project context, trimmed to fit within token budget
- Agents can also read `CONTEXT.md` directly from filesystem
- Dashboard provides UI to view/edit/search all memory files with markdown preview

**Storage:** Memory files are plain markdown on the filesystem (not SQLite). The dashboard reads/writes them directly. The `CONTEXT.md` is regenerated when memory files change (via file watcher → SSE event → optional auto-recompile).

## Q10: Expected scale

- Agents: 5 (Jim, Dwight, Pam, Mike, Kelly) — never more than ~20
- Projects: ~10-20 active, maybe 100 total
- Events/hour: low volume, maybe 50-200 during active work sessions
- Sessions per agent: dozens to hundreds of JSONL files, largest ~1.5MB
- No pagination needed; lazy-load large session files
