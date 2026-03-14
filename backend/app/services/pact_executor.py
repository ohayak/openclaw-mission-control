"""
PACT executor service — spawns pact CLI subprocesses.

Architecture:
  - Lock file at /tmp/pact-{project_id}.lock prevents double-spawn
  - Log file at /tmp/pact-{project_id}.log captures stdout+stderr
  - Subprocess inherits environment (ANTHROPIC_API_KEY comes from parent env, env=None)
  - Lock file removed when process exits (via finally block in background thread)
  - is_running() validates the PID in the lock file is still alive (stale-lock self-heal)

State machine:
  idle ──► running ──► idle
             │
             └──► error (process exits non-zero; lock still cleaned up)
"""
import shutil
import subprocess
import threading
import time
from pathlib import Path

LOCK_DIR = Path("/tmp")


def _lock_path(project_id: str) -> Path:
    return LOCK_DIR / f"pact-{project_id}.lock"


def _log_path(project_id: str) -> Path:
    return LOCK_DIR / f"pact-{project_id}.log"


def is_running(project_id: str) -> bool:
    """Return True if a PACT process for project_id is currently alive."""
    lock = _lock_path(project_id)
    if not lock.exists():
        return False
    try:
        pid = int(lock.read_text().strip())
        # Check /proc/{pid} exists (Linux-specific; works in Docker/Linux deployments)
        Path(f"/proc/{pid}").stat()
        return True
    except (ValueError, FileNotFoundError, OSError):
        # Stale lock file — clean it up
        lock.unlink(missing_ok=True)
        return False


def spawn_pact(
    project_id: str,
    project_dir: str,
    args: list[str],
    model_override: str | None = None,
) -> None:
    """
    Spawn `pact <args>` in project_dir.

    Args:
        project_id: UUID string identifying the project (used for lock/log file names)
        project_dir: Absolute path to the PACT project directory
        args: Arguments to pass to the pact CLI (e.g. ["run", "interview", "."])
        model_override: Optional model name to set as ANTHROPIC_MODEL env var.
                        When None, inherits parent environment unchanged.

    Raises:
        RuntimeError: If PACT is already running for this project
        FileNotFoundError: If the pact CLI is not installed/not on PATH
    """
    if is_running(project_id):
        raise RuntimeError(f"PACT is already running for project {project_id}")

    # Check pact is installed before writing lock file
    if shutil.which("pact") is None:
        raise FileNotFoundError(
            "pact CLI not found on PATH. Please install pact before running PACT actions."
        )

    log_path = _log_path(project_id)
    lock_path = _lock_path(project_id)

    # Build environment: inherit parent env, optionally override model
    env: dict | None = None
    if model_override:
        import os
        env = dict(os.environ)
        env["ANTHROPIC_MODEL"] = model_override

    log_file = open(log_path, "a")  # noqa: WPS515 — stays open until thread closes it
    try:
        proc = subprocess.Popen(
            ["pact"] + args,
            cwd=project_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,  # None = inherit parent env; dict = inherit + model override
        )
    except Exception:
        log_file.close()
        raise

    lock_path.write_text(str(proc.pid))

    def _cleanup() -> None:
        """Wait for process to exit, then remove lock file."""
        try:
            proc.wait()
        finally:
            log_file.close()
            lock_path.unlink(missing_ok=True)

    thread = threading.Thread(target=_cleanup, daemon=True)
    thread.start()


def stream_logs(project_id: str):
    """
    Generator: yields log lines from the log file while the process is running.
    Continues reading until the process exits and all lines are consumed.

    Yields:
        str: Log lines (newlines stripped)
    """
    log_path = _log_path(project_id)
    if not log_path.exists():
        return

    with open(log_path) as f:
        while True:
            line = f.readline()
            if line:
                yield line.rstrip("\n")
            elif not is_running(project_id):
                # Process has exited — drain any remaining lines
                remaining = f.read()
                if remaining:
                    for remaining_line in remaining.splitlines():
                        yield remaining_line
                break
            else:
                time.sleep(0.1)


def get_logs(project_id: str) -> str:
    """Return full historical log content for a project."""
    log_path = _log_path(project_id)
    if not log_path.exists():
        return ""
    return log_path.read_text()
