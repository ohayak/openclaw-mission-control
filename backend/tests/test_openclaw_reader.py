"""Tests for the openclaw_reader service."""
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.models import AgentInfo, SessionInfo
import app.services.openclaw_reader as reader_module
from app.services.openclaw_reader import (
    _get_openclaw_config,
    _parse_session_file,
    _read_sessions_for_agent,
    _cache,
    _CACHE_TTL,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the reader cache before each test."""
    _cache.clear()
    yield
    _cache.clear()


class TestGetAllAgents:
    def test_get_all_agents_with_fixture(self, tmp_path):
        """get_all_agents() returns agents from openclaw.json config."""
        fixture_config = FIXTURES / "openclaw.json"

        with patch.object(reader_module, "_get_openclaw_config") as mock_config, \
             patch.object(reader_module, "_get_agents_dir") as mock_dir:
            mock_config.return_value = json.loads(fixture_config.read_text())
            mock_dir.return_value = tmp_path  # empty dir, no sessions

            agents = reader_module.get_all_agents()

        assert len(agents) == 2
        ids = {a.id for a in agents}
        assert "jim" in ids
        assert "dwight" in ids

    def test_agent_fields_populated(self, tmp_path):
        fixture_config = FIXTURES / "openclaw.json"

        with patch.object(reader_module, "_get_openclaw_config") as mock_config, \
             patch.object(reader_module, "_get_agents_dir") as mock_dir:
            mock_config.return_value = json.loads(fixture_config.read_text())
            mock_dir.return_value = tmp_path

            agents = reader_module.get_all_agents()

        jim = next(a for a in agents if a.id == "jim")
        assert jim.name == "Jim"
        assert jim.model == "claude-sonnet-4-6"
        assert jim.identity is not None
        assert jim.identity.emoji == "😏"

    def test_agents_not_active_with_no_sessions(self, tmp_path):
        fixture_config = FIXTURES / "openclaw.json"

        with patch.object(reader_module, "_get_openclaw_config") as mock_config, \
             patch.object(reader_module, "_get_agents_dir") as mock_dir:
            mock_config.return_value = json.loads(fixture_config.read_text())
            mock_dir.return_value = tmp_path

            agents = reader_module.get_all_agents()

        for agent in agents:
            assert agent.is_active is False
            assert agent.total_sessions == 0

    def test_empty_config_returns_empty_list(self):
        with patch.object(reader_module, "_get_openclaw_config") as mock_config:
            mock_config.return_value = {}
            agents = reader_module.get_all_agents()
        assert agents == []


class TestParseSessionFile:
    def test_parse_fixture_session(self, tmp_path):
        """_parse_session_file() correctly parses the fixture JSONL."""
        fixture = FIXTURES / "session.jsonl"
        # Copy to tmp with .jsonl name
        session_file = tmp_path / "abc123.jsonl"
        session_file.write_text(fixture.read_text())

        info = _parse_session_file("jim", session_file, is_active=False)

        assert info is not None
        assert info.agent_id == "jim"
        assert info.id == "abc123"  # from session event in JSONL
        assert info.is_active is False
        assert info.model == "claude-sonnet-4-6"
        assert info.message_count == 4  # 4 assistant messages
        assert info.input_tokens == 15 + 20 + 18 + 25  # from fixture
        assert info.output_tokens == 42 + 85 + 30 + 20  # from fixture

    def test_parse_session_tokens_totaled(self, tmp_path):
        fixture = FIXTURES / "session.jsonl"
        session_file = tmp_path / "test.jsonl"
        session_file.write_text(fixture.read_text())

        info = _parse_session_file("jim", session_file, is_active=False)
        assert info is not None
        assert info.total_tokens == info.input_tokens + info.output_tokens

    def test_parse_session_estimates_cost(self, tmp_path):
        fixture = FIXTURES / "session.jsonl"
        session_file = tmp_path / "test.jsonl"
        session_file.write_text(fixture.read_text())

        info = _parse_session_file("jim", session_file, is_active=False)
        assert info is not None
        # Cost should be positive for known model with tokens
        assert info.estimated_cost > 0.0

    def test_parse_active_session(self, tmp_path):
        fixture = FIXTURES / "session.jsonl"
        session_file = tmp_path / "active.jsonl"
        session_file.write_text(fixture.read_text())

        info = _parse_session_file("jim", session_file, is_active=True)
        assert info is not None
        assert info.is_active is True

    def test_parse_empty_file_returns_none_or_zero_tokens(self, tmp_path):
        session_file = tmp_path / "empty.jsonl"
        session_file.write_text("")

        info = _parse_session_file("jim", session_file, is_active=False)
        # Should not crash; may return None or a zero-token result
        if info is not None:
            assert info.message_count == 0
            assert info.total_tokens == 0

    def test_parse_malformed_json_lines_graceful(self, tmp_path):
        session_file = tmp_path / "malformed.jsonl"
        session_file.write_text(
            '{"type":"session","id":"xyz","timestamp":"2024-01-01T00:00:00Z","cwd":"/"}\n'
            'this is not json\n'
            '{"type":"message","message":{"role":"assistant","usage":{"input":10,"output":5},"model":"claude-haiku-4-5"}}\n'
        )

        info = _parse_session_file("jim", session_file, is_active=False)
        assert info is not None
        assert info.id == "xyz"
        assert info.input_tokens == 10
        assert info.output_tokens == 5

    def test_parse_missing_file_returns_none(self, tmp_path):
        missing = tmp_path / "nonexistent.jsonl"
        info = _parse_session_file("jim", missing, is_active=False)
        assert info is None


class TestCachingBehavior:
    def test_config_cache_hit_within_ttl(self, tmp_path):
        """Second call within TTL returns cached value without re-reading file."""
        config_file = tmp_path / "openclaw.json"
        config_data = {"agents": {"list": [{"id": "test", "name": "Test"}]}}
        config_file.write_text(json.dumps(config_data))

        with patch("app.services.openclaw_reader.settings") as mock_settings:
            mock_settings.OPENCLAW_CONFIG_PATH = str(config_file)
            mock_settings.OPENCLAW_AGENTS_DIR = str(tmp_path)

            # First call — populates cache
            result1 = _get_openclaw_config()

        # Now mutate the file
        config_data["agents"]["list"].append({"id": "new_agent", "name": "New"})
        config_file.write_text(json.dumps(config_data))

        with patch("app.services.openclaw_reader.settings") as mock_settings:
            mock_settings.OPENCLAW_CONFIG_PATH = str(config_file)
            # Second call — should return cached result (without new_agent)
            result2 = _get_openclaw_config()

        # Cache key is shared; both results should be same dict
        assert result1 == result2

    def test_sessions_cache_hit_within_ttl(self, tmp_path):
        """_read_sessions_for_agent() returns same list on second call within TTL."""
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()

        fixture = FIXTURES / "session.jsonl"
        (session_dir / "abc123.jsonl").write_text(fixture.read_text())

        sessions1 = _read_sessions_for_agent("jim", session_dir)
        # Add another session file
        (session_dir / "def456.jsonl").write_text(fixture.read_text())

        sessions2 = _read_sessions_for_agent("jim", session_dir)

        # Should be the same cached result (1 session, not 2)
        assert sessions1 is sessions2
        assert len(sessions2) == 1

    def test_cache_expires_after_ttl(self, tmp_path):
        """After TTL, cache is invalidated and fresh data is read."""
        _cache.clear()
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()

        fixture = FIXTURES / "session.jsonl"
        (session_dir / "abc123.jsonl").write_text(fixture.read_text())

        sessions1 = _read_sessions_for_agent("jim", session_dir)

        # Expire the cache manually by backdating its timestamp
        cache_key = f"sessions:{session_dir}"
        if cache_key in _cache:
            value, ts = _cache[cache_key]
            _cache[cache_key] = (value, ts - _CACHE_TTL - 1)

        # Add another session file
        (session_dir / "def456.jsonl").write_text(fixture.read_text())

        sessions2 = _read_sessions_for_agent("jim", session_dir)

        assert len(sessions1) == 1
        assert len(sessions2) == 2


class TestMissingFiles:
    def test_missing_config_returns_empty(self):
        _cache.clear()  # Clear any cached real config before testing
        with patch("app.services.openclaw_reader.settings") as mock_settings:
            mock_settings.OPENCLAW_CONFIG_PATH = "/nonexistent/path/openclaw.json"
            result = _get_openclaw_config()
        assert result == {}

    def test_missing_session_dir_returns_empty(self, tmp_path):
        missing_dir = tmp_path / "nonexistent" / "sessions"
        sessions = _read_sessions_for_agent("nobody", missing_dir)
        assert sessions == []
