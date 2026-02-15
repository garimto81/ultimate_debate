"""OpenAI Provider 테스트.

OpenAIProvider의 OAuth 메서드 검증:
- get_auth_url(): Codex CLI 호환 인증 URL 생성
- exchange_code(): 콜백 URL 파싱 및 토큰 교환
- login(): Browser OAuth 플로우
- refresh(): 토큰 갱신
- validate(): userinfo 엔드포인트 검증
- get_account_info(): 계정 정보 조회
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from ultimate_debate.auth.providers.base import AuthToken
from ultimate_debate.auth.providers.openai_provider import OpenAIProvider


class TestOpenAIProviderInit:
    """OpenAIProvider 초기화 테스트."""

    def test_default_client_id(self):
        """기본 Client ID 사용 검증."""
        provider = OpenAIProvider()
        assert provider.client_id == "app_EMoamEEZ73f0CkXaXp7hrann"

    def test_custom_client_id(self):
        """커스텀 Client ID 설정 검증."""
        provider = OpenAIProvider(client_id="custom-id")
        assert provider.client_id == "custom-id"

    def test_name_property(self):
        """name 프로퍼티 검증."""
        provider = OpenAIProvider()
        assert provider.name == "openai"

    def test_display_name_property(self):
        """display_name 프로퍼티 검증."""
        provider = OpenAIProvider()
        assert provider.display_name == "OpenAI (ChatGPT Plus/Pro)"


class TestGetAuthUrl:
    """get_auth_url() 테스트."""

    def test_url_contains_correct_endpoint(self):
        """인증 URL에 올바른 엔드포인트 포함 검증."""
        provider = OpenAIProvider()
        url = provider.get_auth_url()
        assert url.startswith("https://auth.openai.com/oauth/authorize?")

    def test_url_contains_client_id(self):
        """인증 URL에 client_id 포함 검증."""
        provider = OpenAIProvider()
        url = provider.get_auth_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["client_id"] == ["app_EMoamEEZ73f0CkXaXp7hrann"]

    def test_url_contains_pkce_params(self):
        """인증 URL에 PKCE 파라미터 포함 검증."""
        provider = OpenAIProvider()
        url = provider.get_auth_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "code_challenge" in params
        assert params["code_challenge_method"] == ["S256"]

    def test_url_contains_scope(self):
        """인증 URL에 scope 포함 검증."""
        provider = OpenAIProvider()
        url = provider.get_auth_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "openid" in params["scope"][0]
        assert "offline_access" in params["scope"][0]

    def test_url_contains_state(self):
        """인증 URL에 state 포함 검증."""
        provider = OpenAIProvider()
        url = provider.get_auth_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "state" in params
        assert len(params["state"][0]) > 20

    def test_url_contains_redirect_uri(self):
        """인증 URL에 redirect_uri 포함 검증 (포트 1455)."""
        provider = OpenAIProvider()
        url = provider.get_auth_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "localhost:1455" in params["redirect_uri"][0]

    def test_pkce_state_stored(self):
        """get_auth_url 호출 후 PKCE와 state 저장 검증."""
        provider = OpenAIProvider()
        provider.get_auth_url()
        assert provider._pkce is not None
        assert provider._state is not None
        assert provider._redirect_uri is not None


class TestExchangeCode:
    """exchange_code() 테스트."""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self):
        """토큰 교환 성공 검증."""
        provider = OpenAIProvider()
        provider._pkce = MagicMock()
        provider._pkce.code_verifier = "test-verifier"
        provider._redirect_uri = "http://localhost:1455/auth/callback"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "at-test-123",
            "refresh_token": "rt-test-456",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid profile email",
        }

        with patch(
            "ultimate_debate.auth.providers.openai_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            callback = (
                "http://localhost:1455/auth/callback"
                "?code=test-code&state=test-state"
            )
            token = await provider.exchange_code(callback)

        assert isinstance(token, AuthToken)
        assert token.access_token == "at-test-123"
        assert token.refresh_token == "rt-test-456"
        assert token.provider == "openai"
        assert token.token_type == "Bearer"

    @pytest.mark.asyncio
    async def test_exchange_code_error_in_url(self):
        """콜백 URL에 error 파라미터 시 예외 검증."""
        provider = OpenAIProvider()

        callback = (
            "http://localhost:1455/auth/callback"
            "?error=access_denied"
            "&error_description=User+denied+access"
        )

        with pytest.raises(ValueError, match="인증 실패"):
            await provider.exchange_code(callback)

    @pytest.mark.asyncio
    async def test_exchange_code_no_code(self):
        """콜백 URL에 code 없을 시 예외 검증."""
        provider = OpenAIProvider()

        callback = "http://localhost:1455/auth/callback?state=test"

        with pytest.raises(ValueError, match="code 파라미터"):
            await provider.exchange_code(callback)

    @pytest.mark.asyncio
    async def test_exchange_code_api_failure(self):
        """토큰 교환 API 실패 검증."""
        provider = OpenAIProvider()
        provider._pkce = MagicMock()
        provider._pkce.code_verifier = "test-verifier"
        provider._redirect_uri = "http://localhost:1455/auth/callback"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "invalid_grant"

        with patch(
            "ultimate_debate.auth.providers.openai_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            callback = (
                "http://localhost:1455/auth/callback"
                "?code=expired-code&state=test"
            )
            with pytest.raises(ValueError, match="토큰 교환 실패"):
                await provider.exchange_code(callback)


class TestLogin:
    """login() 테스트."""

    @pytest.mark.asyncio
    async def test_login_calls_browser_oauth(self):
        """login()이 BrowserOAuth.authenticate 호출 검증."""
        provider = OpenAIProvider()

        mock_token_response = MagicMock()
        mock_token_response.access_token = "at-login"
        mock_token_response.refresh_token = "rt-login"
        mock_token_response.token_type = "Bearer"
        mock_token_response.expires_in = 3600
        mock_token_response.scope = "openid profile"

        with patch.object(
            provider, "_try_codex_cli_token", return_value=None
        ), patch(
            "ultimate_debate.auth.providers.openai_provider.BrowserOAuth"
        ) as mock_oauth:
            mock_instance = MagicMock()
            mock_instance.authenticate = AsyncMock(
                return_value=mock_token_response
            )
            mock_oauth.return_value = mock_instance

            token = await provider.login()

        assert isinstance(token, AuthToken)
        assert token.access_token == "at-login"
        assert token.provider == "openai"

    @pytest.mark.asyncio
    async def test_login_manual_mode(self):
        """수동 모드 login 검증."""
        provider = OpenAIProvider()

        mock_token_response = MagicMock()
        mock_token_response.access_token = "at-manual"
        mock_token_response.refresh_token = None
        mock_token_response.token_type = "Bearer"
        mock_token_response.expires_in = 3600
        mock_token_response.scope = "openid"

        with patch.object(
            provider, "_try_codex_cli_token", return_value=None
        ), patch(
            "ultimate_debate.auth.providers.openai_provider.BrowserOAuth"
        ) as mock_oauth:
            mock_instance = MagicMock()
            mock_instance.authenticate = AsyncMock(
                return_value=mock_token_response
            )
            mock_oauth.return_value = mock_instance

            token = await provider.login(manual_mode=True)

            # manual_callback=True로 BrowserOAuth 생성 검증
            call_kwargs = mock_oauth.call_args
            assert call_kwargs[1]["manual_callback"] is True

        assert token.access_token == "at-manual"

    @pytest.mark.asyncio
    async def test_login_oauth_failure(self):
        """OAuth 인증 실패 시 ValueError 검증."""
        provider = OpenAIProvider()

        from ultimate_debate.auth.flows.browser_oauth import (
            OAuthCallbackError,
        )

        with patch.object(
            provider, "_try_codex_cli_token", return_value=None
        ), patch(
            "ultimate_debate.auth.providers.openai_provider.BrowserOAuth"
        ) as mock_oauth:
            mock_instance = MagicMock()
            mock_instance.authenticate = AsyncMock(
                side_effect=OAuthCallbackError("timeout")
            )
            mock_oauth.return_value = mock_instance

            with pytest.raises(ValueError, match="OpenAI 인증 실패"):
                await provider.login()

    @pytest.mark.asyncio
    async def test_login_codex_cli_token_reuse(self):
        """Codex CLI 토큰 재사용 검증."""
        provider = OpenAIProvider()

        codex_token = AuthToken(
            provider="openai",
            access_token="codex-at",
            refresh_token="codex-rt",
            expires_at=datetime.now() + timedelta(hours=1),
        )

        with patch.object(
            provider, "_try_codex_cli_token", return_value=codex_token
        ):
            token = await provider.login()

        assert token.access_token == "codex-at"

    @pytest.mark.asyncio
    async def test_login_no_device_code_param(self):
        """login()에 use_device_code 파라미터 없음 검증."""
        import inspect

        sig = inspect.signature(OpenAIProvider.login)
        assert "use_device_code" not in sig.parameters

    def test_no_login_device_code_method(self):
        """login_device_code 메서드 제거 검증."""
        provider = OpenAIProvider()
        assert not hasattr(provider, "login_device_code")


class TestRefresh:
    """refresh() 테스트."""

    @pytest.mark.asyncio
    async def test_refresh_success(self):
        """토큰 갱신 성공 검증."""
        provider = OpenAIProvider()

        old_token = AuthToken(
            provider="openai",
            access_token="old-at",
            refresh_token="valid-rt",
            expires_at=datetime.now() - timedelta(hours=1),
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-at",
            "refresh_token": "new-rt",
            "token_type": "Bearer",
            "expires_in": 7200,
            "scope": "openid profile",
        }

        with patch(
            "ultimate_debate.auth.providers.openai_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            new_token = await provider.refresh(old_token)

        assert new_token.access_token == "new-at"
        assert new_token.refresh_token == "new-rt"
        assert new_token.provider == "openai"

    @pytest.mark.asyncio
    async def test_refresh_no_refresh_token(self):
        """refresh_token 없을 시 예외 검증."""
        provider = OpenAIProvider()

        token = AuthToken(
            provider="openai",
            access_token="at",
            refresh_token=None,
            expires_at=datetime.now() - timedelta(hours=1),
        )

        with pytest.raises(ValueError, match="Refresh token"):
            await provider.refresh(token)

    @pytest.mark.asyncio
    async def test_refresh_api_failure(self):
        """토큰 갱신 API 실패 검증."""
        provider = OpenAIProvider()

        token = AuthToken(
            provider="openai",
            access_token="at",
            refresh_token="bad-rt",
            expires_at=datetime.now() - timedelta(hours=1),
        )

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "invalid_grant"

        with patch(
            "ultimate_debate.auth.providers.openai_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            with pytest.raises(ValueError, match="토큰 갱신 실패"):
                await provider.refresh(token)

    @pytest.mark.asyncio
    async def test_refresh_preserves_old_refresh_token(self):
        """갱신 응답에 refresh_token 없으면 기존 값 유지 검증."""
        provider = OpenAIProvider()

        old_token = AuthToken(
            provider="openai",
            access_token="old-at",
            refresh_token="keep-this-rt",
            expires_at=datetime.now() - timedelta(hours=1),
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-at",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with patch(
            "ultimate_debate.auth.providers.openai_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post.return_value = mock_response

            new_token = await provider.refresh(old_token)

        assert new_token.refresh_token == "keep-this-rt"


class TestValidate:
    """validate() 테스트."""

    @pytest.mark.asyncio
    async def test_validate_expired_token(self):
        """만료된 토큰 검증."""
        provider = OpenAIProvider()

        token = AuthToken(
            provider="openai",
            access_token="expired-at",
            expires_at=datetime.now() - timedelta(hours=1),
        )

        result = await provider.validate(token)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_uses_userinfo_endpoint(self):
        """validate()가 auth.openai.com/userinfo 사용 검증."""
        provider = OpenAIProvider()

        token = AuthToken(
            provider="openai",
            access_token="valid-at",
            expires_at=datetime.now() + timedelta(hours=1),
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch(
            "ultimate_debate.auth.providers.openai_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get.return_value = mock_response

            result = await provider.validate(token)

            # 호출된 URL 확인
            call_args = mock_instance.get.call_args
            assert call_args[0][0] == "https://auth.openai.com/userinfo"

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_invalid_token(self):
        """유효하지 않은 토큰 검증."""
        provider = OpenAIProvider()

        token = AuthToken(
            provider="openai",
            access_token="invalid-at",
            expires_at=datetime.now() + timedelta(hours=1),
        )

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch(
            "ultimate_debate.auth.providers.openai_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get.return_value = mock_response

            result = await provider.validate(token)

        assert result is False


class TestGetAccountInfo:
    """get_account_info() 테스트."""

    @pytest.mark.asyncio
    async def test_get_account_info_success(self):
        """계정 정보 조회 성공 검증."""
        provider = OpenAIProvider()

        token = AuthToken(
            provider="openai",
            access_token="valid-at",
            expires_at=datetime.now() + timedelta(hours=1),
        )

        user_info = {
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test User",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = user_info

        with patch(
            "ultimate_debate.auth.providers.openai_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get.return_value = mock_response

            result = await provider.get_account_info(token)

        assert result == user_info
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_account_info_failure(self):
        """계정 정보 조회 실패 시 None 반환 검증."""
        provider = OpenAIProvider()

        token = AuthToken(
            provider="openai",
            access_token="invalid-at",
            expires_at=datetime.now() + timedelta(hours=1),
        )

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch(
            "ultimate_debate.auth.providers.openai_provider.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get.return_value = mock_response

            result = await provider.get_account_info(token)

        assert result is None


class TestLogout:
    """logout() 테스트."""

    @pytest.mark.asyncio
    async def test_logout_returns_true(self):
        """logout()이 항상 True 반환 검증."""
        provider = OpenAIProvider()

        token = AuthToken(
            provider="openai",
            access_token="at",
            expires_at=datetime.now() + timedelta(hours=1),
        )

        result = await provider.logout(token)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
