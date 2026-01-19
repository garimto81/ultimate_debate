"""Device Code Flow Tests

RFC 8628 Device Authorization Grant 테스트.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

# 테스트 대상 - 아직 구현 안됨 (RED 단계)
from ultimate_debate.auth.flows.device_code import (
    DeviceCodeOAuth,
    DeviceCodeResponse,
    DeviceCodeConfig,
    DeviceCodeError,
)


class TestDeviceCodeResponse:
    """DeviceCodeResponse 데이터클래스 테스트."""

    def test_create_response(self):
        """DeviceCodeResponse 생성 테스트."""
        response = DeviceCodeResponse(
            device_code="device_123",
            user_code="ABCD-1234",
            verification_uri="https://auth.openai.com/activate",
            expires_in=900,
            interval=5,
        )

        assert response.device_code == "device_123"
        assert response.user_code == "ABCD-1234"
        assert response.verification_uri == "https://auth.openai.com/activate"
        assert response.expires_in == 900
        assert response.interval == 5

    def test_optional_verification_uri_complete(self):
        """verification_uri_complete는 선택적."""
        response = DeviceCodeResponse(
            device_code="device_123",
            user_code="ABCD-1234",
            verification_uri="https://auth.openai.com/activate",
            verification_uri_complete="https://auth.openai.com/activate?user_code=ABCD-1234",
            expires_in=900,
            interval=5,
        )

        assert response.verification_uri_complete == "https://auth.openai.com/activate?user_code=ABCD-1234"


class TestDeviceCodeConfig:
    """DeviceCodeConfig 설정 테스트."""

    def test_create_config(self):
        """기본 설정 생성 테스트."""
        config = DeviceCodeConfig(
            client_id="test_client_id",
            device_authorization_endpoint="https://auth.example.com/device/code",
            token_endpoint="https://auth.example.com/token",
            scope="openid profile",
        )

        assert config.client_id == "test_client_id"
        assert config.device_authorization_endpoint == "https://auth.example.com/device/code"
        assert config.token_endpoint == "https://auth.example.com/token"
        assert config.scope == "openid profile"


class TestDeviceCodeOAuth:
    """DeviceCodeOAuth 테스트."""

    @pytest.fixture
    def config(self):
        """테스트용 설정."""
        return DeviceCodeConfig(
            client_id="DRivsnm2Mu42T3KOpqdtwB3NYviHYzwD",
            device_authorization_endpoint="https://auth.openai.com/oauth/device/code",
            token_endpoint="https://auth.openai.com/oauth/token",
            scope="openid profile email offline_access",
        )

    @pytest.fixture
    def oauth(self, config):
        """DeviceCodeOAuth 인스턴스."""
        return DeviceCodeOAuth(config)

    @pytest.mark.asyncio
    async def test_request_device_code_success(self, oauth):
        """device code 요청 성공 테스트."""
        mock_response = {
            "device_code": "dev_code_123",
            "user_code": "WXYZ-5678",
            "verification_uri": "https://auth.openai.com/activate",
            "verification_uri_complete": "https://auth.openai.com/activate?user_code=WXYZ-5678",
            "expires_in": 900,
            "interval": 5,
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )

            result = await oauth.request_device_code()

        assert isinstance(result, DeviceCodeResponse)
        assert result.device_code == "dev_code_123"
        assert result.user_code == "WXYZ-5678"
        assert result.verification_uri == "https://auth.openai.com/activate"

    @pytest.mark.asyncio
    async def test_request_device_code_failure(self, oauth):
        """device code 요청 실패 테스트."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=400,
                text="Bad Request"
            )

            with pytest.raises(DeviceCodeError) as exc:
                await oauth.request_device_code()

            assert "device code 요청 실패" in str(exc.value)

    @pytest.mark.asyncio
    async def test_poll_for_token_success(self, oauth):
        """토큰 폴링 성공 테스트."""
        mock_token_response = {
            "access_token": "access_123",
            "refresh_token": "refresh_456",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid profile email offline_access",
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_token_response
            )

            # TokenResponse는 browser_oauth에서 import
            from ultimate_debate.auth.flows.browser_oauth import TokenResponse
            result = await oauth.poll_for_token(
                device_code="dev_code_123",
                interval=1,
                timeout=10,
            )

        assert isinstance(result, TokenResponse)
        assert result.access_token == "access_123"
        assert result.refresh_token == "refresh_456"

    @pytest.mark.asyncio
    async def test_poll_for_token_pending(self, oauth):
        """토큰 폴링 - authorization_pending 상태 테스트."""
        pending_response = {
            "error": "authorization_pending",
            "error_description": "The user has not yet authorized the request",
        }
        success_response = {
            "access_token": "access_123",
            "refresh_token": "refresh_456",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        call_count = 0

        def mock_post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return MagicMock(
                    status_code=400,
                    json=lambda: pending_response
                )
            return MagicMock(
                status_code=200,
                json=lambda: success_response
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post_side_effect):
            result = await oauth.poll_for_token(
                device_code="dev_code_123",
                interval=0.1,  # 테스트용 짧은 간격
                timeout=10,
            )

        assert result.access_token == "access_123"
        assert call_count >= 3  # 최소 3번 호출

    @pytest.mark.asyncio
    async def test_poll_for_token_slow_down(self, oauth):
        """토큰 폴링 - slow_down 응답 시 interval 증가 테스트."""
        slow_down_response = {
            "error": "slow_down",
            "error_description": "Please slow down",
        }
        success_response = {
            "access_token": "access_123",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        call_count = 0

        def mock_post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(
                    status_code=400,
                    json=lambda: slow_down_response
                )
            return MagicMock(
                status_code=200,
                json=lambda: success_response
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post_side_effect):
            # slow_down 시 interval이 증가해야 함
            result = await oauth.poll_for_token(
                device_code="dev_code_123",
                interval=1,
                timeout=30,
            )

        assert result.access_token == "access_123"

    @pytest.mark.asyncio
    async def test_poll_for_token_expired(self, oauth):
        """토큰 폴링 - 만료 테스트."""
        expired_response = {
            "error": "expired_token",
            "error_description": "The device code has expired",
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=400,
                json=lambda: expired_response
            )

            with pytest.raises(DeviceCodeError) as exc:
                await oauth.poll_for_token(
                    device_code="dev_code_123",
                    interval=1,
                    timeout=5,
                )

            assert "expired" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_poll_for_token_access_denied(self, oauth):
        """토큰 폴링 - 사용자 거부 테스트."""
        denied_response = {
            "error": "access_denied",
            "error_description": "The user denied the request",
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=400,
                json=lambda: denied_response
            )

            with pytest.raises(DeviceCodeError) as exc:
                await oauth.poll_for_token(
                    device_code="dev_code_123",
                    interval=1,
                    timeout=5,
                )

            assert "denied" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_poll_for_token_timeout(self, oauth):
        """토큰 폴링 - 타임아웃 테스트."""
        pending_response = {
            "error": "authorization_pending",
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=400,
                json=lambda: pending_response
            )

            with pytest.raises(DeviceCodeError) as exc:
                await oauth.poll_for_token(
                    device_code="dev_code_123",
                    interval=0.1,
                    timeout=0.3,  # 매우 짧은 타임아웃
                )

            assert "timeout" in str(exc.value).lower() or "시간 초과" in str(exc.value)


class TestDeviceCodeInstructions:
    """사용자 안내 출력 테스트."""

    @pytest.fixture
    def config(self):
        return DeviceCodeConfig(
            client_id="test_client",
            device_authorization_endpoint="https://auth.example.com/device/code",
            token_endpoint="https://auth.example.com/token",
            scope="openid",
        )

    def test_display_instructions(self, config, capsys):
        """사용자 안내 메시지 출력 테스트."""
        oauth = DeviceCodeOAuth(config)
        device_response = DeviceCodeResponse(
            device_code="dev_123",
            user_code="TEST-CODE",
            verification_uri="https://example.com/activate",
            expires_in=900,
            interval=5,
        )

        oauth.display_instructions(device_response)

        captured = capsys.readouterr()
        # Rich console 출력은 capsys로 캡처되지 않을 수 있음
        # 최소한 에러 없이 실행되는지 확인


class TestDeviceCodeFullFlow:
    """전체 Device Code Flow 통합 테스트."""

    @pytest.fixture
    def config(self):
        return DeviceCodeConfig(
            client_id="DRivsnm2Mu42T3KOpqdtwB3NYviHYzwD",
            device_authorization_endpoint="https://auth.openai.com/oauth/device/code",
            token_endpoint="https://auth.openai.com/oauth/token",
            scope="openid profile email offline_access",
        )

    @pytest.mark.asyncio
    async def test_full_authenticate_flow(self, config):
        """전체 인증 플로우 테스트 (모킹)."""
        oauth = DeviceCodeOAuth(config)

        device_response = {
            "device_code": "dev_code_full",
            "user_code": "FULL-1234",
            "verification_uri": "https://auth.openai.com/activate",
            "expires_in": 900,
            "interval": 5,
        }

        token_response = {
            "access_token": "full_access_token",
            "refresh_token": "full_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid profile email offline_access",
        }

        call_count = 0

        def mock_post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # device code 요청
                return MagicMock(
                    status_code=200,
                    json=lambda: device_response
                )
            elif call_count == 2:
                # 첫 번째 폴링 - pending
                return MagicMock(
                    status_code=400,
                    json=lambda: {"error": "authorization_pending"}
                )
            else:
                # 두 번째 폴링 - 성공
                return MagicMock(
                    status_code=200,
                    json=lambda: token_response
                )

        with patch("httpx.AsyncClient.post", side_effect=mock_post_side_effect):
            with patch.object(oauth, "display_instructions"):  # 출력 억제
                result = await oauth.authenticate(timeout=10, poll_interval=0.1)

        assert result.access_token == "full_access_token"
        assert result.refresh_token == "full_refresh_token"
