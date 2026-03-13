"""
File watcher service — monitors OpenClaw/PACT dirs and emits events.
Uses watchdog for filesystem monitoring.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_watcher_started = False


def start_watcher() -> None:
    """Start the background file watcher if watchdog is available."""
    global _watcher_started
    if _watcher_started:
        return

    try:
        from watchdog.events import FileSystemEvent, FileSystemEventHandler
        from watchdog.observers import Observer

        from app.services.event_bus import event_bus

        class OpenClawHandler(FileSystemEventHandler):
            def on_created(self, event: FileSystemEvent) -> None:  # type: ignore[override]
                if event.is_directory:
                    return
                path = str(event.src_path)
                self._handle(path, "created")

            def on_modified(self, event: FileSystemEvent) -> None:  # type: ignore[override]
                if event.is_directory:
                    return
                path = str(event.src_path)
                self._handle(path, "modified")

            def _handle(self, path: str, action: str) -> None:
                filename = Path(path).name

                # Session lock files → agent became active
                if filename.endswith(".jsonl.lock"):
                    agent_id = _extract_agent_id(path)
                    event_bus.emit_activity(
                        "agent_active",
                        f"Agent {agent_id} session started",
                        agent_id=agent_id,
                    )
                # PACT state changes
                elif filename == "state.json" and ".pact" in path:
                    event_bus.emit_activity(
                        "pact_phase",
                        f"PACT state changed: {path}",
                        metadata={"path": path},
                    )
                # PACT audit events
                elif filename == "audit.jsonl" and ".pact" in path:
                    event_bus.emit_activity(
                        "pact_audit",
                        f"PACT audit updated: {path}",
                        metadata={"path": path},
                    )

        def _extract_agent_id(path: str) -> str:
            """Extract agent id from path like /data/.openclaw/agents/<id>/sessions/..."""
            parts = Path(path).parts
            try:
                idx = parts.index("agents")
                return parts[idx + 1]
            except (ValueError, IndexError):
                return "unknown"

        observer = Observer()
        agents_dir = settings.OPENCLAW_AGENTS_DIR
        pact_dir = settings.PACT_PROJECTS_DIR

        if os.path.exists(agents_dir):
            observer.schedule(OpenClawHandler(), agents_dir, recursive=True)
        if os.path.exists(pact_dir):
            observer.schedule(OpenClawHandler(), pact_dir, recursive=True)

        observer.daemon = True
        observer.start()
        _watcher_started = True
        logger.info("File watcher started for %s and %s", agents_dir, pact_dir)

    except ImportError:
        logger.warning("watchdog not installed — file watching disabled")
    except Exception as e:
        logger.warning("Failed to start file watcher: %s", e)
