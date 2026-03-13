"""
OpenClaw reader service — reads openclaw.json and session JSONL files.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.models import AgentIdentity, AgentInfo, SessionInfo


def _get_openclaw_config() -> dict[str, Any]:
    """Load and return the openclaw.json config dict."""
    config_path = Path(settings.OPENCLAW_CONFIG_PATH)
    if not config_path.exists():
        return {}
    try:
        with open(config_path) as f:
            return json.load(f)
    except Exception:
        return {}


def _get_agents_dir() -> Path:
    return Path(settings.OPENCLAW_AGENTS_DIR)


def get_all_agents() -> list[AgentInfo]:
    """Read all agents from openclaw.json and enrich with session stats."""
    config = _get_openclaw_config()
    agents_raw: list[dict] = config.get("agents", {}).get("list", [])
    agents_dir = _get_agents_dir()

    result = []
    for raw in agents_raw:
        agent_id = raw.get("id", "")
        identity_raw = raw.get("identity", {})
        identity = AgentIdentity(
            name=identity_raw.get("name", raw.get("name", agent_id)),
            emoji=identity_raw.get("emoji"),
            avatar=identity_raw.get("avatar"),
            theme=identity_raw.get("theme"),
        )

        # Get session stats
        session_dir = agents_dir / agent_id / "sessions"
        sessions = _read_sessions_for_agent(agent_id, session_dir)

        is_active = any(s.is_active for s in sessions)
        total_input = sum(s.input_tokens for s in sessions)
        total_output = sum(s.output_tokens for s in sessions)

        info = AgentInfo(
            id=agent_id,
            name=raw.get("name", agent_id),
            workspace=raw.get("workspace"),
            model=raw.get("model"),
            identity=identity,
            is_active=is_active,
            active_session_count=sum(1 for s in sessions if s.is_active),
            total_sessions=len(sessions),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
        )
        result.append(info)
    return result


def get_agent_by_id(agent_id: str) -> AgentInfo | None:
    agents = get_all_agents()
    for a in agents:
        if a.id == agent_id:
            return a
    return None


def get_sessions_for_agent(agent_id: str) -> list[SessionInfo]:
    session_dir = _get_agents_dir() / agent_id / "sessions"
    return _read_sessions_for_agent(agent_id, session_dir)


def _read_sessions_for_agent(agent_id: str, session_dir: Path) -> list[SessionInfo]:
    if not session_dir.exists():
        return []

    sessions: list[SessionInfo] = []
    try:
        for f in session_dir.iterdir():
            # Only process .jsonl files (not .lock, .reset.*, .deleted.*)
            if not f.name.endswith(".jsonl"):
                continue
            # Check if there's a lock file (active session)
            lock_file = Path(str(f) + ".lock")
            is_active = lock_file.exists()

            info = _parse_session_file(agent_id, f, is_active)
            if info:
                sessions.append(info)
    except Exception:
        pass

    sessions.sort(key=lambda s: s.started_at or "", reverse=True)
    return sessions


def _parse_session_file(agent_id: str, path: Path, is_active: bool) -> SessionInfo | None:
    """Parse a session JSONL file and extract metadata + token counts."""
    try:
        started_at = None
        cwd = None
        message_count = 0
        input_tokens = 0
        output_tokens = 0
        model = None
        session_id = path.stem  # UUID from filename

        with open(path, errors="replace") as f:
            for line_no, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = obj.get("type")

                if event_type == "session":
                    started_at = obj.get("timestamp")
                    cwd = obj.get("cwd")
                    session_id = obj.get("id", session_id)

                elif event_type == "message":
                    msg = obj.get("message", {})
                    if msg.get("role") == "assistant":
                        message_count += 1
                        usage = msg.get("usage", {})
                        input_tokens += usage.get("input", 0)
                        output_tokens += usage.get("output", 0)
                        if not model:
                            model = msg.get("model")

                # Stop reading after 10K lines to avoid huge files stalling
                if line_no > 10000:
                    break

        return SessionInfo(
            id=session_id,
            agent_id=agent_id,
            filename=path.name,
            is_active=is_active,
            started_at=started_at,
            cwd=cwd,
            message_count=message_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            model=model,
        )
    except Exception:
        return None


def get_token_usage_by_agent() -> dict[str, dict]:
    """Returns per-agent token totals: {agent_id: {input, output, total, sessions}}"""
    config = _get_openclaw_config()
    agents_raw: list[dict] = config.get("agents", {}).get("list", [])
    agents_dir = _get_agents_dir()
    result = {}

    for raw in agents_raw:
        agent_id = raw.get("id", "")
        session_dir = agents_dir / agent_id / "sessions"
        sessions = _read_sessions_for_agent(agent_id, session_dir)
        result[agent_id] = {
            "agent_id": agent_id,
            "agent_name": raw.get("name", agent_id),
            "total_input_tokens": sum(s.input_tokens for s in sessions),
            "total_output_tokens": sum(s.output_tokens for s in sessions),
            "total_tokens": sum(s.total_tokens for s in sessions),
            "session_count": len(sessions),
        }

    return result
