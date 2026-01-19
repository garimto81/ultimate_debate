"""Claude AI Client Tests

TDD: RED 단계 - 실패하는 테스트 먼저 작성
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# 테스트할 클래스 임포트 (아직 구현되지 않음)
from ultimate_debate.clients.claude_client import ClaudeClient
from ultimate_debate.clients.base import BaseAIClient


class TestClaudeClientInit:
    """ClaudeClient 초기화 테스트"""

    def test_inherits_from_base_ai_client(self):
        """BaseAIClient를 상속해야 함"""
        client = ClaudeClient()
        assert isinstance(client, BaseAIClient)

    def test_default_model_name(self):
        """기본 모델명은 claude-3-5-sonnet"""
        client = ClaudeClient()
        assert client.model_name == "claude-3-5-sonnet"

    def test_custom_model_name(self):
        """커스텀 모델명 설정 가능"""
        client = ClaudeClient(model_name="claude-3-opus")
        assert client.model_name == "claude-3-opus"

    def test_has_token_store(self):
        """TokenStore를 가지고 있어야 함"""
        client = ClaudeClient()
        assert hasattr(client, "token_store")


class TestClaudeClientAuthentication:
    """ClaudeClient 인증 테스트"""

    @pytest.mark.asyncio
    async def test_ensure_authenticated_returns_bool(self):
        """ensure_authenticated는 bool을 반환"""
        client = ClaudeClient()
        with patch.object(client, "_get_claude_code_token", return_value="test-token"):
            result = await client.ensure_authenticated()
            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_reuses_claude_code_token(self):
        """Claude Code 토큰 재사용 - 저장된 토큰 없을 때"""
        client = ClaudeClient()
        # TokenStore에 저장된 토큰이 없는 경우 Claude Code 토큰 사용
        with patch.object(client.token_store, "load", new_callable=AsyncMock) as load_mock:
            load_mock.return_value = None  # 저장된 토큰 없음
            with patch.object(
                client, "_get_claude_code_token", return_value="test-token"
            ) as token_mock:
                with patch.object(client.token_store, "save", new_callable=AsyncMock):
                    result = await client.ensure_authenticated()
                    token_mock.assert_called_once()
                    assert result is True


class TestClaudeClientAnalyze:
    """ClaudeClient.analyze() 테스트"""

    @pytest.mark.asyncio
    async def test_analyze_returns_dict(self):
        """analyze()는 dict를 반환"""
        client = ClaudeClient()
        mock_response = {
            "analysis": "테스트 분석",
            "conclusion": "테스트 결론",
            "confidence": 0.9,
            "key_points": ["포인트1"],
            "suggested_steps": ["단계1"],
        }
        with patch.object(client, "_call_api", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await client.analyze("테스트 태스크")
            assert isinstance(result, dict)
            assert "analysis" in result
            assert "conclusion" in result
            assert "confidence" in result

    @pytest.mark.asyncio
    async def test_analyze_with_context(self):
        """analyze()에 context 전달"""
        client = ClaudeClient()
        mock_response = {
            "analysis": "테스트 분석",
            "conclusion": "테스트 결론",
            "confidence": 0.9,
        }
        with patch.object(client, "_call_api", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            context = {"previous_round": "결과"}
            result = await client.analyze("태스크", context)
            assert result == mock_response


class TestClaudeClientReview:
    """ClaudeClient.review() 테스트"""

    @pytest.mark.asyncio
    async def test_review_returns_dict(self):
        """review()는 dict를 반환"""
        client = ClaudeClient()
        mock_response = {
            "feedback": "피드백",
            "agreement_points": ["동의1"],
            "disagreement_points": ["불동의1"],
            "suggested_improvements": ["개선1"],
        }
        with patch.object(client, "_call_api", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await client.review(
                task="태스크",
                peer_analysis={"analysis": "피어 분석"},
                own_analysis={"analysis": "본인 분석"},
            )
            assert isinstance(result, dict)
            assert "feedback" in result
            assert "agreement_points" in result
            assert "disagreement_points" in result


class TestClaudeClientDebate:
    """ClaudeClient.debate() 테스트"""

    @pytest.mark.asyncio
    async def test_debate_returns_dict(self):
        """debate()는 dict를 반환"""
        client = ClaudeClient()
        mock_response = {
            "updated_position": {
                "conclusion": "업데이트된 결론",
                "confidence": 0.85,
                "key_points": ["포인트"],
            },
            "rebuttals": ["반박1"],
            "concessions": ["수용1"],
            "remaining_disagreements": ["남은 불일치"],
        }
        with patch.object(client, "_call_api", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await client.debate(
                task="태스크",
                own_position={"conclusion": "본인 입장"},
                opposing_views=[{"conclusion": "상대 입장"}],
            )
            assert isinstance(result, dict)
            assert "updated_position" in result
            assert "rebuttals" in result
            assert "concessions" in result


class TestClaudeClientAPICall:
    """ClaudeClient._call_api() 테스트"""

    @pytest.mark.asyncio
    async def test_call_api_uses_anthropic_endpoint(self):
        """Anthropic API 엔드포인트 사용"""
        client = ClaudeClient()
        assert client.API_BASE == "https://api.anthropic.com/v1"

    @pytest.mark.asyncio
    async def test_call_api_handles_401(self):
        """401 응답 시 재인증 시도"""
        client = ClaudeClient()
        with patch.object(client, "ensure_authenticated", new_callable=AsyncMock) as auth_mock:
            with patch("httpx.AsyncClient") as client_mock:
                mock_response = MagicMock()
                mock_response.status_code = 401
                client_mock.return_value.__aenter__.return_value.post.return_value = (
                    mock_response
                )

                # 두 번째 호출은 성공
                auth_mock.return_value = True
                # 실제 테스트는 구현 후 완성
