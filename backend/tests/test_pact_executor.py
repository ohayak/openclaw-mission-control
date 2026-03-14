"""Tests for the pact_executor service."""
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.pact_executor import (
    _lock_path,
    _log_path,
    get_logs,
    is_running,
    spawn_pact,
    stream_logs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_id() -> str:
    return "test-project-abc123"


@pytest.fixture(autouse=True)
def clean_lock_and_log(project_id: str, tmp_path: Path):
    """Ensure lock and log files are cleaned up after each test."""
    yield
    _lock_path(project_id).unlink(missing_ok=True)
    _log_path(project_id).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tests for is_running
# ---------------------------------------------------------------------------


class TestIsRunning:
    def test_returns_false_when_no_lock_file(self, project_id: str):
        assert is_running(project_id) is False

    def test_returns_true_when_valid_pid_in_lock(self, project_id: str):
        import os

        # Write our own PID — current process is definitely running
        _lock_path(project_id).write_text(str(os.getpid()))
        assert is_running(project_id) is True

    def test_returns_false_and_cleans_stale_lock(self, project_id: str):
        # PID 99999999 almost certainly doesn't exist
        _lock_path(project_id).write_text("99999999")
        assert is_running(project_id) is False
        assert not _lock_path(project_id).exists()

    def test_returns_false_and_cleans_malformed_lock(self, project_id: str):
        _lock_path(project_id).write_text("not-a-pid")
        assert is_running(project_id) is False
        assert not _lock_path(project_id).exists()

    def test_returns_false_and_cleans_empty_lock(self, project_id: str):
        _lock_path(project_id).write_text("")
        assert is_running(project_id) is False
        assert not _lock_path(project_id).exists()


# ---------------------------------------------------------------------------
# Tests for spawn_pact
# ---------------------------------------------------------------------------


class TestSpawnPact:
    def test_raises_runtime_error_when_already_running(self, project_id: str, tmp_path: Path):
        import os

        _lock_path(project_id).write_text(str(os.getpid()))
        with pytest.raises(RuntimeError, match="already running"):
            spawn_pact(project_id, str(tmp_path), ["run", "."])

    def test_raises_file_not_found_when_pact_not_installed(
        self, project_id: str, tmp_path: Path
    ):
        with patch("shutil.which", return_value=None):
            with pytest.raises(FileNotFoundError, match="pact CLI not found"):
                spawn_pact(project_id, str(tmp_path), ["run", "."])

    def test_spawns_process_and_writes_lock_file(self, project_id: str, tmp_path: Path):
        with patch("shutil.which", return_value="/usr/local/bin/pact"):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.wait.return_value = 0
            with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
                spawn_pact(project_id, str(tmp_path), ["init", "."])
                mock_popen.assert_called_once_with(
                    ["pact", "init", "."],
                    cwd=str(tmp_path),
                    stdout=mock_popen.call_args.kwargs["stdout"],
                    stderr=-2,  # subprocess.STDOUT
                    env=None,
                )
        lock = _lock_path(project_id)
        assert lock.exists()
        assert lock.read_text().strip() == "12345"

    def test_lock_file_removed_after_process_exits(self, project_id: str, tmp_path: Path):
        cleanup_done = threading.Event()

        def wait_side_effect():
            time.sleep(0.05)
            cleanup_done.set()

        with patch("shutil.which", return_value="/usr/local/bin/pact"):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.wait.side_effect = wait_side_effect
            with patch("subprocess.Popen", return_value=mock_proc):
                spawn_pact(project_id, str(tmp_path), ["run", "."])

        # Lock file should exist immediately after spawn
        assert _lock_path(project_id).exists()

        # Wait for background thread to finish
        cleanup_done.wait(timeout=2.0)
        time.sleep(0.05)  # allow finally block to execute

        assert not _lock_path(project_id).exists()

    def test_lock_file_removed_even_on_process_error(self, project_id: str, tmp_path: Path):
        cleanup_done = threading.Event()

        def wait_side_effect():
            time.sleep(0.05)
            cleanup_done.set()
            return 1  # non-zero exit

        with patch("shutil.which", return_value="/usr/local/bin/pact"):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.wait.side_effect = wait_side_effect
            with patch("subprocess.Popen", return_value=mock_proc):
                spawn_pact(project_id, str(tmp_path), ["run", "."])

        cleanup_done.wait(timeout=2.0)
        time.sleep(0.05)

        assert not _lock_path(project_id).exists()

    def test_inherits_environment_env_none(self, project_id: str, tmp_path: Path):
        """Verify env=None is passed to Popen (inherits parent env, no key storage)."""
        with patch("shutil.which", return_value="/usr/local/bin/pact"):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.wait.return_value = 0
            with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
                spawn_pact(project_id, str(tmp_path), ["run", "."])
                assert mock_popen.call_args.kwargs["env"] is None

    def test_spawns_with_correct_args(self, project_id: str, tmp_path: Path):
        with patch("shutil.which", return_value="/usr/local/bin/pact"):
            mock_proc = MagicMock()
            mock_proc.pid = 99
            mock_proc.wait.return_value = 0
            with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
                spawn_pact(project_id, str(tmp_path), ["run", "interview", "."])
                assert mock_popen.call_args.args[0] == ["pact", "run", "interview", "."]


# ---------------------------------------------------------------------------
# Tests for get_logs
# ---------------------------------------------------------------------------


class TestGetLogs:
    def test_returns_empty_string_when_no_log_file(self, project_id: str):
        assert get_logs(project_id) == ""

    def test_returns_log_content_when_file_exists(self, project_id: str):
        _log_path(project_id).write_text("line 1\nline 2\nline 3\n")
        result = get_logs(project_id)
        assert result == "line 1\nline 2\nline 3\n"

    def test_returns_empty_log_when_file_is_empty(self, project_id: str):
        _log_path(project_id).write_text("")
        assert get_logs(project_id) == ""


# ---------------------------------------------------------------------------
# Tests for stream_logs
# ---------------------------------------------------------------------------


class TestStreamLogs:
    def test_yields_nothing_when_no_log_file(self, project_id: str):
        lines = list(stream_logs(project_id))
        assert lines == []

    def test_yields_existing_lines_when_process_not_running(self, project_id: str):
        _log_path(project_id).write_text("alpha\nbeta\ngamma\n")
        # No lock file → is_running returns False → stream drains existing content
        lines = list(stream_logs(project_id))
        assert lines == ["alpha", "beta", "gamma"]

    def test_strips_newlines_from_lines(self, project_id: str):
        _log_path(project_id).write_text("hello\nworld\n")
        lines = list(stream_logs(project_id))
        assert all("\n" not in line for line in lines)

    def test_yields_empty_file_gracefully(self, project_id: str):
        _log_path(project_id).write_text("")
        lines = list(stream_logs(project_id))
        assert lines == []

    def test_streams_lines_written_during_run(self, project_id: str):
        """Simulate a process writing to the log file while stream_logs is reading."""
        import os

        log_path = _log_path(project_id)
        lock_path = _lock_path(project_id)

        log_path.write_text("")
        lock_path.write_text(str(os.getpid()))  # simulate running

        collected: list[str] = []
        stop_event = threading.Event()

        def _write_log():
            """Write log lines then remove lock to signal completion."""
            time.sleep(0.05)
            log_path.write_text("line1\nline2\n")
            time.sleep(0.05)
            lock_path.unlink(missing_ok=True)
            stop_event.set()

        writer = threading.Thread(target=_write_log, daemon=True)
        writer.start()

        # stream_logs should terminate once the lock is gone
        for line in stream_logs(project_id):
            collected.append(line)

        stop_event.wait(timeout=3.0)
        assert "line1" in collected
        assert "line2" in collected
