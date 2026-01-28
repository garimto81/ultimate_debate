"""Test Claude Code token discovery and error messages."""
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ultimate_debate.clients.claude_client import ClaudeClient


class TestClaudeTokenDiscovery:
    """Claude Code 토큰 검색 및 에러 메시지 테스트."""

    def test_token_not_found_returns_none(self, tmp_path):
        """토큰 없을 때 None 반환."""
        client = ClaudeClient("claude-3-5-sonnet")

        # 모든 토큰 경로를 빈 디렉토리로 mock
        env_vars = {"APPDATA": str(tmp_path), "LOCALAPPDATA": str(tmp_path)}
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch.dict("os.environ", env_vars),
        ):
            result = client._get_claude_code_token()

        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_authenticated_failure_message(self, tmp_path):
        """ensure_authenticated 실패 시 해결 방법 안내."""
        client = ClaudeClient("claude-3-5-sonnet")

        # TokenStore mock (저장된 토큰 없음)
        async def mock_load(provider):
            return None

        mock_store = MagicMock()
        mock_store.load = mock_load
        client.token_store = mock_store

        env_vars = {"APPDATA": str(tmp_path), "LOCALAPPDATA": str(tmp_path)}
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch.dict("os.environ", env_vars),
        ):
            result = await client.ensure_authenticated()

        # ensure_authenticated는 False 반환 (예외 발생 안 함)
        assert result is False

    def test_token_search_paths_logged(self, tmp_path, caplog):
        """토큰 검색 시도한 경로들이 로그에 기록됨."""
        client = ClaudeClient("claude-3-5-sonnet")

        env_vars = {"APPDATA": str(tmp_path), "LOCALAPPDATA": str(tmp_path)}
        with (
            caplog.at_level(logging.DEBUG),
            patch.object(Path, "home", return_value=tmp_path),
            patch.dict("os.environ", env_vars),
        ):
            client._get_claude_code_token()

        # 로그에 시도한 경로 정보 포함 확인
        log_messages = [record.message for record in caplog.records]
        # 적어도 하나의 경로 확인 로그가 있어야 함
        assert any("토큰 경로 확인" in msg for msg in log_messages)

    def test_valid_token_file_parsed_correctly(self, tmp_path):
        """유효한 토큰 파일이 올바르게 파싱됨."""
        client = ClaudeClient("claude-3-5-sonnet")

        # Claude Code 토큰 파일 구조 mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        credentials_file = claude_dir / "credentials.json"

        # 토큰 파일 작성
        credentials_file.write_text(json.dumps({"access_token": "test-token-12345"}))

        with patch.object(Path, "home", return_value=tmp_path):
            result = client._get_claude_code_token()

        assert result == "test-token-12345"

    def test_corrupted_token_file_handled_gracefully(self, tmp_path):
        """손상된 토큰 파일 처리 시 graceful 실패."""
        client = ClaudeClient("claude-3-5-sonnet")

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        credentials_file = claude_dir / "credentials.json"
        credentials_file.write_text("invalid json {{{")

        with patch.object(Path, "home", return_value=tmp_path):
            result = client._get_claude_code_token()

        # 예외 발생하지 않고 None 반환
        assert result is None

    def test_multiple_token_keys_checked(self, tmp_path):
        """다양한 토큰 키 형식 시도."""
        client = ClaudeClient("claude-3-5-sonnet")

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        credentials_file = claude_dir / "credentials.json"

        # auth_token 키 사용
        credentials_file.write_text(json.dumps({"auth_token": "auth-token-value"}))

        with patch.object(Path, "home", return_value=tmp_path):
            result = client._get_claude_code_token()

        assert result == "auth-token-value"

    def test_token_not_found_logs_all_tried_paths(self, tmp_path, caplog):
        """토큰 없을 때 시도한 모든 경로를 로그에 기록."""
        client = ClaudeClient("claude-3-5-sonnet")

        env_vars = {"APPDATA": str(tmp_path), "LOCALAPPDATA": str(tmp_path)}
        with (
            caplog.at_level(logging.WARNING),
            patch.object(Path, "home", return_value=tmp_path),
            patch.dict("os.environ", env_vars),
        ):
            client._get_claude_code_token()

        # WARNING 로그에 시도한 경로 목록 포함
        warning_logs = [
            record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        ]
        assert any("토큰을 찾을 수 없음" in msg for msg in warning_logs)
        assert any("시도한 경로" in msg for msg in warning_logs)
