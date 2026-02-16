"""Browser OAuth Flow 테스트.

Race condition 수정 및 콜백 처리 검증.
"""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, patch

import pytest

from ultimate_debate.auth.flows.browser_oauth import (
    BrowserOAuth,
    OAuthCallbackError,
    OAuthConfig,
    PKCEChallenge,
    TokenResponse,
    _callback_events,
    _callback_lock,
    _callback_results,
    generate_pkce_challenge,
)


class TestPKCE:
    """PKCE 챌린지 생성 테스트."""

    def test_generate_pkce_challenge(self):
        """PKCE 챌린지 생성 검증."""
        challenge = generate_pkce_challenge()

        assert isinstance(challenge, PKCEChallenge)
        assert len(challenge.code_verifier) > 40
        assert len(challenge.code_challenge) > 40
        assert challenge.code_challenge_method == "S256"

    def test_pkce_uniqueness(self):
        """PKCE 챌린지 고유성 검증."""
        c1 = generate_pkce_challenge()
        c2 = generate_pkce_challenge()

        assert c1.code_verifier != c2.code_verifier
        assert c1.code_challenge != c2.code_challenge


class TestBrowserOAuth:
    """BrowserOAuth 클래스 테스트."""

    @pytest.fixture
    def oauth_config(self) -> OAuthConfig:
        """테스트용 OAuth 설정."""
        return OAuthConfig(
            client_id="test-client",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="http://localhost:{port}/auth/callback",
            scope="openid profile",
        )

    def test_init_with_auto_port(self, oauth_config):
        """자동 포트 할당 검증."""
        oauth = BrowserOAuth(oauth_config)
        assert oauth.port > 0
        assert "{port}" not in oauth.config.redirect_uri

    def test_init_with_fixed_port(self, oauth_config):
        """고정 포트 할당 검증."""
        oauth = BrowserOAuth(oauth_config, fixed_port=8888)
        assert oauth.port == 8888
        assert "8888" in oauth.config.redirect_uri

    def test_build_authorization_url(self, oauth_config):
        """인증 URL 생성 검증."""
        oauth = BrowserOAuth(oauth_config, fixed_port=9999)
        url = oauth._build_authorization_url()

        assert "https://auth.example.com/authorize" in url
        assert "client_id=test-client" in url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A9999" in url
        assert "response_type=code" in url
        assert "scope=openid+profile" in url
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert "state=" in url


class TestCallbackEventSync:
    """콜백 이벤트 동기화 테스트."""

    def test_event_set_on_callback(self):
        """콜백 수신 시 이벤트 설정 검증."""
        test_state = "test-state-123"
        event = threading.Event()

        with _callback_lock:
            _callback_events[test_state] = event

        # 콜백 결과 시뮬레이션
        with _callback_lock:
            _callback_results[test_state] = {
                "auth_code": "test-code",
                "error": None
            }
            if test_state in _callback_events:
                _callback_events[test_state].set()

        # 이벤트가 설정되었는지 확인
        assert event.is_set()

        # 정리
        with _callback_lock:
            del _callback_results[test_state]
            del _callback_events[test_state]

    def test_event_wait_timeout(self):
        """이벤트 대기 타임아웃 검증."""
        event = threading.Event()

        # 0.1초 타임아웃으로 대기 (콜백 없음)
        start = time.time()
        result = event.wait(timeout=0.1)
        elapsed = time.time() - start

        assert result is False  # 타임아웃
        assert elapsed >= 0.1

    def test_event_wait_success(self):
        """이벤트 대기 성공 검증."""
        event = threading.Event()

        # 별도 스레드에서 0.05초 후 이벤트 설정
        def set_event():
            time.sleep(0.05)
            event.set()

        thread = threading.Thread(target=set_event)
        thread.start()

        # 이벤트 대기 (1초 타임아웃)
        start = time.time()
        result = event.wait(timeout=1.0)
        elapsed = time.time() - start

        thread.join()

        assert result is True  # 성공
        assert elapsed < 0.5  # 0.05초 근처에서 완료


class TestTokenExchange:
    """토큰 교환 테스트."""

    @pytest.fixture
    def oauth(self) -> BrowserOAuth:
        """테스트용 BrowserOAuth 인스턴스."""
        config = OAuthConfig(
            client_id="test-client",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="http://localhost:{port}/auth/callback",
            scope="openid profile",
        )
        return BrowserOAuth(config, fixed_port=9999)

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, oauth):
        """토큰 교환 성공 검증."""
        mock_response_data = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid profile",
        }

        with patch(
            "ultimate_debate.auth.flows.browser_oauth.httpx.AsyncClient"
        ) as mock_client:
            # 비동기 컨텍스트 매니저 설정
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # response 객체 설정 (json()은 동기 메서드)
            from unittest.mock import MagicMock
            mock_response_obj = MagicMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response_data
            mock_instance.post.return_value = mock_response_obj

            token = await oauth._exchange_code_for_token("test-code")

            assert isinstance(token, TokenResponse)
            assert token.access_token == "test-access-token"
            assert token.refresh_token == "test-refresh-token"
            assert token.token_type == "Bearer"
            assert token.expires_in == 3600

    @pytest.mark.asyncio
    async def test_exchange_code_failure(self, oauth):
        """토큰 교환 실패 검증."""
        with patch(
            "ultimate_debate.auth.flows.browser_oauth.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            from unittest.mock import MagicMock
            mock_response_obj = MagicMock()
            mock_response_obj.status_code = 400
            mock_response_obj.text = "Invalid code"
            mock_instance.post.return_value = mock_response_obj

            with pytest.raises(OAuthCallbackError) as exc_info:
                await oauth._exchange_code_for_token("invalid-code")

            assert "토큰 교환 실패" in str(exc_info.value)


class TestCallbackUrlParsing:
    """콜백 URL 파싱 테스트."""

    @pytest.fixture
    def oauth(self) -> BrowserOAuth:
        """테스트용 BrowserOAuth 인스턴스."""
        config = OAuthConfig(
            client_id="test-client",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="http://localhost:{port}/auth/callback",
            scope="openid profile",
        )
        return BrowserOAuth(config, fixed_port=9999)

    def test_parse_callback_url_success(self, oauth):
        """콜백 URL 파싱 성공 검증."""
        url = "http://localhost:9999/auth/callback?code=abc123&state=xyz789"
        code, state = oauth._parse_callback_url(url)

        assert code == "abc123"
        assert state == "xyz789"

    def test_parse_callback_url_error(self, oauth):
        """콜백 URL 에러 파싱 검증."""
        url = "http://localhost:9999/auth/callback?error=access_denied&error_description=User+denied"

        with pytest.raises(OAuthCallbackError) as exc_info:
            oauth._parse_callback_url(url)

        assert "User denied" in str(exc_info.value)

    def test_parse_callback_url_no_code(self, oauth):
        """콜백 URL에 code 없음 검증."""
        url = "http://localhost:9999/auth/callback?state=xyz789"

        with pytest.raises(OAuthCallbackError) as exc_info:
            oauth._parse_callback_url(url)

        assert "code" in str(exc_info.value)
