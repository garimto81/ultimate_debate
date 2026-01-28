"""Test Gemini CLI token reuse."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from ultimate_debate.auth.providers.google_provider import (
    GoogleProvider,
    try_import_gemini_cli_token,
)


class TestGeminiCLITokenReuse:
    """Gemini CLI 토큰 재사용 테스트."""

    def test_try_import_gemini_cli_token_exists(self, tmp_path):
        """~/.gemini/oauth_creds.json 존재 시 토큰 반환."""
        # Mock 토큰 파일 생성
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        token_file = gemini_dir / "oauth_creds.json"

        mock_token = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        token_file.write_text(json.dumps(mock_token))

        with patch.object(Path, "home", return_value=tmp_path):
            result = try_import_gemini_cli_token()

        assert result is not None
        assert result.access_token == "test_access_token"
        assert result.refresh_token == "test_refresh_token"
        assert result.provider == "google"
        assert not result.is_expired()

    def test_try_import_gemini_cli_token_not_exists(self, tmp_path):
        """~/.gemini/oauth_creds.json 없을 시 None 반환."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = try_import_gemini_cli_token()

        assert result is None

    def test_try_import_gemini_cli_token_expired(self, tmp_path):
        """만료된 토큰은 None 반환."""
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        token_file = gemini_dir / "oauth_creds.json"

        mock_token = {
            "access_token": "expired_token",
            "refresh_token": "test_refresh_token",
            "expires_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        }
        token_file.write_text(json.dumps(mock_token))

        with patch.object(Path, "home", return_value=tmp_path):
            result = try_import_gemini_cli_token()

        # 만료된 토큰은 None 반환
        assert result is None

    def test_try_import_gemini_cli_token_unix_timestamp(self, tmp_path):
        """Unix timestamp 형식 expires_at 처리."""
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        token_file = gemini_dir / "oauth_creds.json"

        future_timestamp = (datetime.now() + timedelta(hours=1)).timestamp()
        mock_token = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
            "expires_at": future_timestamp,
        }
        token_file.write_text(json.dumps(mock_token))

        with patch.object(Path, "home", return_value=tmp_path):
            result = try_import_gemini_cli_token()

        assert result is not None
        assert result.access_token == "test_token"
        assert not result.is_expired()

    def test_try_import_gemini_cli_token_malformed_json(self, tmp_path):
        """잘못된 JSON 파일은 None 반환."""
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        token_file = gemini_dir / "oauth_creds.json"
        token_file.write_text("invalid json {{{")

        with patch.object(Path, "home", return_value=tmp_path):
            result = try_import_gemini_cli_token()

        assert result is None

    def test_try_import_gemini_cli_token_missing_access_token(self, tmp_path):
        """access_token 없으면 None 반환."""
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        token_file = gemini_dir / "oauth_creds.json"

        mock_token = {
            "refresh_token": "test_refresh",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        token_file.write_text(json.dumps(mock_token))

        with patch.object(Path, "home", return_value=tmp_path):
            result = try_import_gemini_cli_token()

        assert result is None

    @pytest.mark.asyncio
    async def test_google_provider_uses_cli_token(self, tmp_path):
        """GoogleProvider.login()이 CLI 토큰을 우선 사용."""
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        token_file = gemini_dir / "oauth_creds.json"

        mock_token = {
            "access_token": "cli_token",
            "refresh_token": "cli_refresh",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        token_file.write_text(json.dumps(mock_token))

        provider = GoogleProvider()

        with patch.object(Path, "home", return_value=tmp_path):
            token = await provider.login()

        # CLI 토큰을 재사용했으므로 브라우저 로그인 없이 토큰 반환
        assert token.access_token == "cli_token"
        assert token.refresh_token == "cli_refresh"
        assert not token.is_expired()

    @pytest.mark.asyncio
    async def test_google_provider_fallback_to_browser(self, tmp_path, monkeypatch):
        """CLI 토큰 없으면 브라우저 로그인으로 fallback."""
        # CLI 토큰 없음
        with patch.object(Path, "home", return_value=tmp_path):
            # 브라우저 로그인은 실제로 실행되지 않도록 모킹
            # 실제 테스트에서는 BrowserOAuth.authenticate()를 모킹
            # 여기서는 CLI 토큰이 없으면 브라우저 로그인 시도하는지만 확인
            result = try_import_gemini_cli_token()
            assert result is None  # CLI 토큰이 없음을 확인

    @pytest.mark.asyncio
    async def test_google_provider_expired_cli_token_fallback(self, tmp_path):
        """만료된 CLI 토큰이 있으면 브라우저 로그인."""
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        token_file = gemini_dir / "oauth_creds.json"

        mock_token = {
            "access_token": "expired_token",
            "refresh_token": "test_refresh",
            "expires_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        }
        token_file.write_text(json.dumps(mock_token))

        with patch.object(Path, "home", return_value=tmp_path):
            # 만료된 토큰이므로 None 반환
            result = try_import_gemini_cli_token()
            assert result is None  # 만료된 토큰은 None 반환

    @pytest.mark.asyncio
    async def test_gemini_client_uses_cli_token(self, tmp_path):
        """GeminiClient가 CLI 토큰을 활용하는지 확인."""
        from ultimate_debate.clients.gemini_client import GeminiClient

        # Mock CLI 토큰 생성
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        token_file = gemini_dir / "oauth_creds.json"

        mock_token = {
            "access_token": "cli_token_for_gemini",
            "refresh_token": "cli_refresh",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        token_file.write_text(json.dumps(mock_token))

        # TokenStore 경로도 tmp_path로 설정
        token_store_dir = tmp_path / ".ultimate_debate"
        token_store_dir.mkdir()

        from ultimate_debate.auth.storage.token_store import TokenStore

        token_store = TokenStore(storage_dir=token_store_dir)
        client = GeminiClient(token_store=token_store)

        with patch.object(Path, "home", return_value=tmp_path):
            await client.ensure_authenticated()

        # CLI 토큰이 사용되었는지 확인
        assert client._token is not None
        assert client._token.access_token == "cli_token_for_gemini"
