"""OpenAI Client 테스트.

OpenAIClient의 인증 및 API 호출 검증:
- ensure_authenticated(): 토큰 로드 → 검증 → 갱신 → 로그인 플로우
- _call_codex_api(): Codex API 스트리밍 응답 파싱
- analyze/review/debate: JSON 파싱 및 fallback
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ultimate_debate.auth.providers.base import AuthToken
from ultimate_debate.clients.openai_client import OpenAIClient


def _make_token(expired: bool = False, refresh: str | None = "rt") -> AuthToken:
    """테스트용 AuthToken 생성."""
    if expired:
        expires_at = datetime.now() - timedelta(hours=1)
    else:
        expires_at = datetime.now() + timedelta(hours=1)
    return AuthToken(
        provider="openai",
        access_token="test-at",
        refresh_token=refresh,
        expires_at=expires_at,
    )


class TestEnsureAuthenticated:
    """ensure_authenticated() 테스트."""

    @pytest.mark.asyncio
    async def test_valid_stored_token(self):
        """유효한 저장 토큰 사용 검증."""
        client = OpenAIClient("gpt-4o")
        valid_token = _make_token()

        client.token_store = MagicMock()
        client.token_store.load = AsyncMock(return_value=valid_token)

        result = await client.ensure_authenticated()

        assert result is True
        assert client._token == valid_token
        client.token_store.load.assert_awaited_once_with("openai")

    @pytest.mark.asyncio
    async def test_expired_token_refresh(self):
        """만료 토큰 갱신 검증."""
        client = OpenAIClient("gpt-4o")
        expired_token = _make_token(expired=True)
        new_token = _make_token()

        client.token_store = MagicMock()
        client.token_store.load = AsyncMock(return_value=expired_token)
        client.token_store.save = AsyncMock()

        client.provider = MagicMock()
        client.provider.refresh = AsyncMock(return_value=new_token)

        result = await client.ensure_authenticated()

        assert result is True
        assert client._token == new_token
        client.provider.refresh.assert_awaited_once_with(expired_token)
        client.token_store.save.assert_awaited_once_with(new_token)

    @pytest.mark.asyncio
    async def test_expired_token_no_refresh_token(self):
        """refresh_token 없는 만료 토큰 → 새 로그인."""
        client = OpenAIClient("gpt-4o")
        expired_token = _make_token(expired=True, refresh=None)
        new_token = _make_token()

        client.token_store = MagicMock()
        client.token_store.load = AsyncMock(return_value=expired_token)
        client.token_store.save = AsyncMock()

        client.provider = MagicMock()
        client.provider.login = AsyncMock(return_value=new_token)

        result = await client.ensure_authenticated()

        assert result is True
        client.provider.login.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_stored_token(self):
        """저장된 토큰 없음 → 새 로그인."""
        client = OpenAIClient("gpt-4o")
        new_token = _make_token()

        client.token_store = MagicMock()
        client.token_store.load = AsyncMock(return_value=None)
        client.token_store.save = AsyncMock()

        client.provider = MagicMock()
        client.provider.login = AsyncMock(return_value=new_token)

        result = await client.ensure_authenticated()

        assert result is True
        client.provider.login.assert_awaited_once()
        client.token_store.save.assert_awaited_once_with(new_token)

    @pytest.mark.asyncio
    async def test_refresh_failure_triggers_login(self):
        """토큰 갱신 실패 시 새 로그인."""
        client = OpenAIClient("gpt-4o")
        expired_token = _make_token(expired=True)
        new_token = _make_token()

        client.token_store = MagicMock()
        client.token_store.load = AsyncMock(return_value=expired_token)
        client.token_store.save = AsyncMock()

        client.provider = MagicMock()
        client.provider.refresh = AsyncMock(
            side_effect=ValueError("refresh failed")
        )
        client.provider.login = AsyncMock(return_value=new_token)

        result = await client.ensure_authenticated()

        assert result is True
        client.provider.login.assert_awaited_once()


class TestCodexApiStreaming:
    """_call_codex_api() 스트리밍 응답 파싱 테스트."""

    @pytest.mark.asyncio
    async def test_streaming_response_parsing(self):
        """Codex API 스트리밍 응답 파싱 검증."""
        client = OpenAIClient("gpt-4o")
        client._token = _make_token()

        # SSE 스트리밍 라인 시뮬레이션
        completed = (
            'data: {"type":"response.completed",'
            '"response":{"model":"gpt-4o-2025-01-01",'
            '"usage":{"input_tokens":10,"output_tokens":5}}}'
        )
        sse_lines = [
            'data: {"type":"response.output_text.delta",'
            '"delta":"Hello"}',
            'data: {"type":"response.output_text.delta",'
            '"delta":" World"}',
            completed,
        ]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = _make_async_iter(sse_lines)

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__.return_value = mock_response
        mock_stream_ctx.__aexit__.return_value = None

        mock_http_client = AsyncMock()
        mock_http_client.stream = MagicMock(return_value=mock_stream_ctx)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_http_client
            mock_cls.return_value.__aexit__.return_value = None

            result = await client._call_codex_api(
                [{"role": "user", "content": "test"}]
            )

        assert result["choices"][0]["message"]["content"] == "Hello World"
        assert result["model"] == "gpt-4o-2025-01-01"

    @pytest.mark.asyncio
    async def test_streaming_reasoning_summary(self):
        """reasoning summary 수집 검증."""
        client = OpenAIClient("gpt-4o")
        client._token = _make_token()

        sse_lines = [
            'data: {"type":"response.reasoning_summary_'
            'text.delta","delta":"Thinking..."}',
            'data: {"type":"response.output_text.delta",'
            '"delta":"Answer"}',
            'data: {"type":"response.completed",'
            '"response":{"model":"gpt-4o","usage":{}}}',
        ]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = _make_async_iter(sse_lines)

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__.return_value = mock_response
        mock_stream_ctx.__aexit__.return_value = None

        mock_http_client = AsyncMock()
        mock_http_client.stream = MagicMock(return_value=mock_stream_ctx)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_http_client
            mock_cls.return_value.__aexit__.return_value = None

            result = await client._call_codex_api(
                [{"role": "user", "content": "test"}]
            )

        assert result["reasoning_summary"] == "Thinking..."

    @pytest.mark.asyncio
    async def test_message_role_conversion(self):
        """system → developer 역할 변환 검증."""
        client = OpenAIClient("gpt-4o")
        client._token = _make_token()

        captured_payload = {}

        sse_lines = [
            'data: {"type":"response.output_text.delta",'
            '"delta":"ok"}',
            'data: {"type":"response.completed",'
            '"response":{"model":"gpt-4o","usage":{}}}',
        ]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = _make_async_iter(sse_lines)

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__.return_value = mock_response
        mock_stream_ctx.__aexit__.return_value = None

        mock_http_client = AsyncMock()

        def capture_stream(*args, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return mock_stream_ctx

        mock_http_client.stream = MagicMock(side_effect=capture_stream)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_http_client
            mock_cls.return_value.__aexit__.return_value = None

            await client._call_codex_api(
                [
                    {"role": "system", "content": "Be helpful"},
                    {"role": "user", "content": "Hello"},
                ]
            )

        # input에 developer 역할이 포함되어야 함
        input_roles = [msg["role"] for msg in captured_payload["input"]]
        assert "developer" in input_roles
        assert "system" not in input_roles


class TestAnalyzeReviewDebate:
    """analyze/review/debate JSON 파싱 및 fallback 테스트."""

    @pytest.fixture
    def client_with_mock_api(self):
        """_call_api가 mock된 클라이언트."""
        client = OpenAIClient("gpt-4o")
        client._token = _make_token()
        return client

    @pytest.mark.asyncio
    async def test_analyze_json_success(self, client_with_mock_api):
        """analyze() JSON 파싱 성공 검증."""
        client = client_with_mock_api
        json_content = (
            '{"analysis": "Good code", "conclusion": "Approved",'
            ' "confidence": 0.9, "key_points": ["clean"]}'
        )

        client._call_api = AsyncMock(
            return_value={
                "choices": [
                    {"message": {"content": json_content}}
                ],
                "model": "gpt-4o",
            }
        )

        result = await client.analyze("Review this code")

        assert result["analysis"] == "Good code"
        assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_analyze_json_fallback(self, client_with_mock_api):
        """analyze() JSON 파싱 실패 시 fallback 검증."""
        client = client_with_mock_api

        client._call_api = AsyncMock(
            return_value={
                "choices": [
                    {"message": {"content": "This is not JSON"}}
                ],
                "model": "gpt-4o",
            }
        )

        result = await client.analyze("Review this code")

        assert result["analysis"] == "This is not JSON"
        assert result["confidence"] == 0.5
        assert result["key_points"] == []

    @pytest.mark.asyncio
    async def test_review_json_fallback(self, client_with_mock_api):
        """review() JSON 파싱 실패 시 fallback 검증."""
        client = client_with_mock_api

        client._call_api = AsyncMock(
            return_value={
                "choices": [
                    {"message": {"content": "Not JSON review"}}
                ],
                "model": "gpt-4o",
            }
        )

        result = await client.review("task", {}, {})

        assert result["feedback"] == "Not JSON review"
        assert result["agreement_points"] == []

    @pytest.mark.asyncio
    async def test_debate_json_fallback(self, client_with_mock_api):
        """debate() JSON 파싱 실패 시 fallback 검증."""
        client = client_with_mock_api

        client._call_api = AsyncMock(
            return_value={
                "choices": [
                    {"message": {"content": "Not JSON debate"}}
                ],
                "model": "gpt-4o",
            }
        )

        result = await client.debate("task", {}, [])

        assert result["updated_position"]["conclusion"] == "Not JSON debate"
        assert result["rebuttals"] == []
        assert result["concessions"] == []


def _make_async_iter(lines):
    """SSE 라인을 비동기 이터레이터로 변환."""

    async def _iter():
        for line in lines:
            yield line

    return _iter


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
