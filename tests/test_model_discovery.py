"""Test model discovery and auto-selection.

로그인 시 API에서 모델 리스트를 조회하여 최고 성능 모델을 자동 선택하는 기능 검증.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ultimate_debate.clients.gemini_client import GeminiClient
from ultimate_debate.clients.openai_client import OpenAIClient


# ===== Gemini Model Discovery =====


class TestGeminiModelDiscovery:
    """Gemini 모델 자동 발견 및 선택 테스트."""

    def test_model_capability_rankings_exist(self):
        """MODEL_CAPABILITY_RANKINGS 클래스 속성이 존재하고 올바른 순서."""
        rankings = GeminiClient.MODEL_CAPABILITY_RANKINGS
        assert isinstance(rankings, dict)
        assert len(rankings) >= 4
        # pro > flash 순서
        assert rankings["gemini-2.5-pro"] > rankings["gemini-2.5-flash"]
        assert rankings["gemini-2.5-flash"] > rankings["gemini-2.0-flash"]

    def test_select_best_model_picks_highest_ranked(self):
        """가용 모델 중 최고 랭킹 모델 선택."""
        client = GeminiClient.__new__(GeminiClient)
        client.model_name = "gemini-2.5-flash"

        best = client._select_best_model(["gemini-2.0-flash", "gemini-2.5-pro", "gemini-1.5-pro"])
        assert best == "gemini-2.5-pro"

    def test_select_best_model_fallback_on_empty(self):
        """모델 리스트가 비어있으면 현재 model_name 유지."""
        client = GeminiClient.__new__(GeminiClient)
        client.model_name = "gemini-2.5-flash"

        best = client._select_best_model([])
        assert best == "gemini-2.5-flash"

    def test_select_best_model_unknown_model_ranked_lowest(self):
        """알 수 없는 모델은 랭킹 0으로 처리."""
        client = GeminiClient.__new__(GeminiClient)
        client.model_name = "gemini-2.5-flash"

        best = client._select_best_model(["unknown-model", "gemini-1.5-flash"])
        assert best == "gemini-1.5-flash"

    @pytest.mark.asyncio
    async def test_discover_models_from_google_ai_api(self):
        """Google AI API에서 모델 리스트 조회 성공."""
        client = GeminiClient.__new__(GeminiClient)
        client._token = MagicMock()
        client._token.access_token = "test-token"
        client._discovered_project_id = "test-project"
        client.use_code_assist = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "models/gemini-2.5-pro",
                    "displayName": "Gemini 2.5 Pro",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-2.5-flash",
                    "displayName": "Gemini 2.5 Flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/text-embedding-004",
                    "displayName": "Text Embedding",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            models = await client._discover_models()

        # generateContent 지원 모델만 반환 (embedding 제외)
        assert "gemini-2.5-pro" in models
        assert "gemini-2.5-flash" in models
        assert "text-embedding-004" not in models

    @pytest.mark.asyncio
    async def test_discover_models_api_failure_returns_empty(self):
        """API 실패 시 빈 리스트 반환."""
        client = GeminiClient.__new__(GeminiClient)
        client._token = MagicMock()
        client._token.access_token = "test-token"
        client._discovered_project_id = "test-project"
        client.use_code_assist = True

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection failed")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            models = await client._discover_models()

        assert models == []

    @pytest.mark.asyncio
    async def test_ensure_authenticated_selects_best_model(self):
        """ensure_authenticated 후 최고 성능 모델 자동 선택."""
        mock_token = MagicMock()
        mock_token.is_expired.return_value = False
        mock_token.access_token = "test-token"

        mock_store = AsyncMock()
        mock_store.load.return_value = mock_token

        client = GeminiClient(token_store=mock_store)
        client._discovered_project_id = "test-project"

        # discover_models mock
        client._discover_models = AsyncMock(
            return_value=["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]
        )
        # _discover_project_id mock (Code Assist 모드)
        client._discover_project_id = AsyncMock()

        await client.ensure_authenticated()

        assert client.model_name == "gemini-2.5-pro"
        assert client.discovered_models == ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]

    @pytest.mark.asyncio
    async def test_ensure_authenticated_keeps_model_when_discovery_fails(self):
        """모델 발견 실패 시 기존 model_name 유지."""
        mock_token = MagicMock()
        mock_token.is_expired.return_value = False
        mock_token.access_token = "test-token"

        mock_store = AsyncMock()
        mock_store.load.return_value = mock_token

        client = GeminiClient(model_name="gemini-2.5-flash", token_store=mock_store)
        client._discovered_project_id = "test-project"
        client._discover_models = AsyncMock(return_value=[])
        client._discover_project_id = AsyncMock()

        await client.ensure_authenticated()

        assert client.model_name == "gemini-2.5-flash"  # 변경 없음


# ===== OpenAI Model Discovery =====


class TestOpenAIModelDiscovery:
    """OpenAI 모델 자동 발견 및 선택 테스트."""

    def test_model_capability_rankings_exist(self):
        """MODEL_CAPABILITY_RANKINGS 클래스 속성이 존재."""
        rankings = OpenAIClient.MODEL_CAPABILITY_RANKINGS
        assert isinstance(rankings, dict)
        assert len(rankings) >= 3

    def test_model_rankings_use_codex_model_names(self):
        """Codex 전용 모델명 사용 확인."""
        rankings = OpenAIClient.MODEL_CAPABILITY_RANKINGS
        # Codex 전용 모델이 포함되어야 함
        assert "gpt-5.3-codex" in rankings
        assert "gpt-5.2-codex" in rankings
        assert "gpt-5.1-codex" in rankings
        # 5.3이 가장 높은 랭킹
        assert rankings["gpt-5.3-codex"] > rankings["gpt-5.2-codex"]
        assert rankings["gpt-5.2-codex"] > rankings["gpt-5.1-codex"]

    def test_select_best_model_picks_highest_ranked(self):
        """가용 모델 중 최고 랭킹 모델 선택."""
        client = OpenAIClient.__new__(OpenAIClient)
        client.model_name = "gpt-5.1-codex"

        best = client._select_best_model(
            ["gpt-5.1-codex", "gpt-5.3-codex", "gpt-5.2-codex"]
        )
        assert best == "gpt-5.3-codex"

    def test_select_best_model_fallback_on_empty(self):
        """모델 리스트가 비어있으면 현재 model_name 유지."""
        client = OpenAIClient.__new__(OpenAIClient)
        client.model_name = "gpt-5.3-codex"

        best = client._select_best_model([])
        assert best == "gpt-5.3-codex"

    @pytest.mark.asyncio
    async def test_discover_models_probes_codex_api(self):
        """Codex API를 프로빙하여 사용 가능 모델 발견."""
        client = OpenAIClient.__new__(OpenAIClient)
        client._token = MagicMock()
        client._token.access_token = "test-token"

        # Codex 전용 모델만 200 응답
        async def mock_post(url, **kwargs):
            model = kwargs.get("json", {}).get("model", "")
            resp = MagicMock()
            if model in ["gpt-5.3-codex", "gpt-5.2-codex"]:
                resp.status_code = 200
            else:
                resp.status_code = 400
                resp.text = '{"detail":"not supported"}'
            return resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            models = await client._discover_models()

        # 최고 랭킹 모델 발견 즉시 종료하므로 1개만
        assert "gpt-5.3-codex" in models

    @pytest.mark.asyncio
    async def test_ensure_authenticated_selects_best_model(self):
        """ensure_authenticated 후 최고 성능 모델 자동 선택."""
        mock_token = MagicMock()
        mock_token.is_expired.return_value = False
        mock_token.access_token = "test-token"
        mock_token.refresh_token = None

        mock_store = AsyncMock()
        mock_store.load.return_value = mock_token

        client = OpenAIClient(token_store=mock_store)
        client._discover_models = AsyncMock(
            return_value=["gpt-5.3-codex", "gpt-5.2-codex"]
        )

        await client.ensure_authenticated()

        assert client.model_name == "gpt-5.3-codex"
        assert hasattr(client, "discovered_models")

    @pytest.mark.asyncio
    async def test_ensure_authenticated_keeps_model_when_discovery_fails(self):
        """모델 발견 실패 시 기존 model_name 유지."""
        mock_token = MagicMock()
        mock_token.is_expired.return_value = False
        mock_token.access_token = "test-token"
        mock_token.refresh_token = None

        mock_store = AsyncMock()
        mock_store.load.return_value = mock_token

        client = OpenAIClient(
            model_name="gpt-5.3-codex", token_store=mock_store
        )
        client._discover_models = AsyncMock(return_value=[])

        await client.ensure_authenticated()

        assert client.model_name == "gpt-5.3-codex"  # 변경 없음
