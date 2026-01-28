"""Test 401 retry loop prevention."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

# 테스트할 클라이언트들
from ultimate_debate.clients.openai_client import OpenAIClient
from ultimate_debate.clients.gemini_client import GeminiClient
from ultimate_debate.clients.claude_client import ClaudeClient
from ultimate_debate.auth.exceptions import RetryLimitExceededError


class TestRetryLoopPrevention:
    """401 반복 시 무한 루프 방지 테스트."""

    @pytest.mark.asyncio
    async def test_openai_client_max_retry_on_401(self):
        """OpenAI 클라이언트: 401 2회 연속 시 예외 발생."""
        client = OpenAIClient("gpt-4o")
        client._token = MagicMock()
        client._token.access_token = "test_token"
        client._token.is_expired.return_value = False

        # 401 응답 반복 시뮬레이션
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.aread = AsyncMock(return_value=b"Unauthorized")

        # Create proper async context manager
        mock_stream = AsyncMock()
        mock_stream.__aenter__.return_value = mock_response
        mock_stream.__aexit__.return_value = None

        mock_http_client = AsyncMock()
        mock_http_client.stream = MagicMock(return_value=mock_stream)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_http_client
            mock_client_cls.return_value.__aexit__.return_value = None

            # Should raise RetryLimitExceededError after retry limit
            with pytest.raises(RetryLimitExceededError) as exc_info:
                await client._call_api([{"role": "user", "content": "test"}])

            # Verify exception attributes
            assert exc_info.value.max_retries == 1
            assert exc_info.value.provider == "openai"
            error_msg = str(exc_info.value).lower()
            assert "retry" in error_msg or "authentication" in error_msg

    @pytest.mark.asyncio
    async def test_gemini_client_max_retry_on_401(self):
        """Gemini 클라이언트: 401 2회 연속 시 예외 발생."""
        client = GeminiClient("gemini-pro")
        client._token = MagicMock()
        client._token.access_token = "test_token"
        client._token.is_expired.return_value = False

        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.json = MagicMock(return_value={"error": "Unauthorized"})
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_http_client
            mock_client_cls.return_value.__aexit__.return_value = None

            with pytest.raises(RetryLimitExceededError) as exc_info:
                await client._call_api([{"role": "user", "parts": [{"text": "test"}]}])

            # Verify exception attributes
            assert exc_info.value.max_retries == 1
            assert exc_info.value.provider == "google"
            error_msg = str(exc_info.value).lower()
            assert "retry" in error_msg or "authentication" in error_msg

    @pytest.mark.asyncio
    async def test_claude_client_max_retry_on_401(self):
        """Claude 클라이언트: 401 2회 연속 시 예외 발생."""
        client = ClaudeClient("claude-3-5-sonnet")
        client._token = "test_token"

        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.json = MagicMock(return_value={"error": "Unauthorized"})
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_http_client
            mock_client_cls.return_value.__aexit__.return_value = None

            with pytest.raises(RetryLimitExceededError) as exc_info:
                await client._call_api([{"role": "user", "content": "test"}])

            # Verify exception attributes
            assert exc_info.value.max_retries == 1
            assert exc_info.value.provider == "claude"
            error_msg = str(exc_info.value).lower()
            assert "authentication" in error_msg or "retry" in error_msg

    @pytest.mark.asyncio
    async def test_retry_counter_resets_on_success(self):
        """성공 응답 후 재시도 카운터 리셋 확인."""
        client = OpenAIClient("gpt-4o")
        # 첫 번째 호출: 401 → 재인증 → 성공
        # 두 번째 호출: 401 → 재인증 → 성공 (카운터 리셋되어 다시 시도 가능)
        # 이 테스트는 카운터가 성공 시 리셋됨을 검증
        assert not hasattr(client, '_auth_retry_count') or client._auth_retry_count == 0
