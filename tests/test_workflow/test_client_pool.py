"""Test ClientPool - graceful degradation for GPT/Gemini clients."""

from unittest.mock import AsyncMock, patch

import pytest

from ultimate_debate.workflow.client_pool import ClientPool


@pytest.mark.asyncio
async def test_pool_initialize_success():
    """Both GPT and Gemini authenticate successfully."""
    with patch(
        "ultimate_debate.workflow.client_pool.OpenAIClient"
    ) as mock_openai, patch(
        "ultimate_debate.workflow.client_pool.GeminiClient"
    ) as mock_gemini:
        mock_openai_inst = AsyncMock()
        mock_openai.return_value = mock_openai_inst
        mock_gemini_inst = AsyncMock()
        mock_gemini.return_value = mock_gemini_inst

        pool = ClientPool()
        await pool.initialize()

        assert "gpt" in pool.available_models
        assert "gemini" in pool.available_models
        mock_openai_inst.ensure_authenticated.assert_awaited_once()
        mock_gemini_inst.ensure_authenticated.assert_awaited_once()


@pytest.mark.asyncio
async def test_pool_gpt_auth_failure():
    """GPT auth fails, Gemini succeeds -> workflow continues."""
    with patch(
        "ultimate_debate.workflow.client_pool.OpenAIClient"
    ) as mock_openai, patch(
        "ultimate_debate.workflow.client_pool.GeminiClient"
    ) as mock_gemini:
        mock_openai_inst = AsyncMock()
        mock_openai_inst.ensure_authenticated.side_effect = Exception("Token expired")
        mock_openai.return_value = mock_openai_inst

        mock_gemini_inst = AsyncMock()
        mock_gemini.return_value = mock_gemini_inst

        pool = ClientPool()
        await pool.initialize()

        assert "gpt" not in pool.available_models
        assert "gemini" in pool.available_models


@pytest.mark.asyncio
async def test_pool_both_auth_failure():
    """Both GPT and Gemini fail -> empty pool, no crash."""
    with patch(
        "ultimate_debate.workflow.client_pool.OpenAIClient"
    ) as mock_openai, patch(
        "ultimate_debate.workflow.client_pool.GeminiClient"
    ) as mock_gemini:
        mock_openai_inst = AsyncMock()
        mock_openai_inst.ensure_authenticated.side_effect = Exception("GPT fail")
        mock_openai.return_value = mock_openai_inst

        mock_gemini_inst = AsyncMock()
        mock_gemini_inst.ensure_authenticated.side_effect = Exception("Gemini fail")
        mock_gemini.return_value = mock_gemini_inst

        pool = ClientPool()
        await pool.initialize()

        assert pool.available_models == []


@pytest.mark.asyncio
async def test_get_client_returns_none_for_unavailable():
    """get_client returns None for unauthenticated model."""
    pool = ClientPool()
    # No initialize called
    client = await pool.get_client("gpt")
    assert client is None


@pytest.mark.asyncio
async def test_get_client_returns_client_for_available():
    """get_client returns client instance for authenticated model."""
    with patch(
        "ultimate_debate.workflow.client_pool.OpenAIClient"
    ) as mock_openai, patch(
        "ultimate_debate.workflow.client_pool.GeminiClient"
    ) as mock_gemini:
        mock_openai_inst = AsyncMock()
        mock_openai.return_value = mock_openai_inst
        mock_gemini_inst = AsyncMock()
        mock_gemini.return_value = mock_gemini_inst

        pool = ClientPool()
        await pool.initialize()

        gpt = await pool.get_client("gpt")
        assert gpt is mock_openai_inst


@pytest.mark.asyncio
async def test_pool_selective_models():
    """Initialize with only specific models."""
    with patch(
        "ultimate_debate.workflow.client_pool.GeminiClient"
    ) as mock_gemini:
        mock_gemini_inst = AsyncMock()
        mock_gemini.return_value = mock_gemini_inst

        pool = ClientPool()
        await pool.initialize(models=["gemini"])

        assert "gemini" in pool.available_models
        assert "gpt" not in pool.available_models


@pytest.mark.asyncio
async def test_pool_close():
    """close() clears all clients and auth status."""
    with patch(
        "ultimate_debate.workflow.client_pool.OpenAIClient"
    ) as mock_openai, patch(
        "ultimate_debate.workflow.client_pool.GeminiClient"
    ) as mock_gemini:
        mock_openai.return_value = AsyncMock()
        mock_gemini.return_value = AsyncMock()

        pool = ClientPool()
        await pool.initialize()
        assert len(pool.available_models) == 2

        await pool.close()
        assert pool.available_models == []
        client = await pool.get_client("gpt")
        assert client is None


@pytest.mark.asyncio
async def test_pool_unknown_model():
    """Unknown model name is ignored during init."""
    pool = ClientPool()
    await pool.initialize(models=["unknown_model"])
    assert pool.available_models == []


@pytest.mark.asyncio
async def test_pool_reinitialize_after_failure():
    """Re-initialize pool after initial failure recovers correctly."""
    with patch(
        "ultimate_debate.workflow.client_pool.OpenAIClient"
    ) as mock_openai, patch(
        "ultimate_debate.workflow.client_pool.GeminiClient"
    ) as mock_gemini:
        # First init: GPT fails
        mock_openai_inst = AsyncMock()
        mock_openai_inst.ensure_authenticated.side_effect = Exception("Token expired")
        mock_openai.return_value = mock_openai_inst

        mock_gemini_inst = AsyncMock()
        mock_gemini.return_value = mock_gemini_inst

        pool = ClientPool()
        await pool.initialize()
        assert "gpt" not in pool.available_models

        # Second init: GPT succeeds (token refreshed)
        mock_openai_inst2 = AsyncMock()
        mock_openai.return_value = mock_openai_inst2

        await pool.initialize()
        assert "gpt" in pool.available_models
        assert "gemini" in pool.available_models


# Phase B Tests: Preflight Health Check


@pytest.mark.asyncio
async def test_health_check_all_healthy():
    """Test health check when all clients are healthy."""
    from ultimate_debate.workflow.client_pool import HealthStatus

    pool = ClientPool()

    # Mock clients
    mock_gpt = AsyncMock()
    mock_gpt.analyze.return_value = {
        "analysis": "OK",
        "conclusion": "OK",
        "confidence": 0.9,
        "model_version": "gpt-5.3-codex"
    }
    pool._clients["gpt"] = mock_gpt
    pool._auth_status["gpt"] = True

    mock_gemini = AsyncMock()
    mock_gemini.analyze.return_value = {
        "analysis": "OK",
        "conclusion": "OK",
        "confidence": 0.9,
        "model_version": "gemini-2.5-pro"
    }
    pool._clients["gemini"] = mock_gemini
    pool._auth_status["gemini"] = True

    health = await pool.health_check(timeout=10.0)

    assert len(health) == 2
    assert health["gpt"].available is True
    assert health["gpt"].latency_ms >= 0  # AsyncMock은 즉시 반환하므로 >= 0
    assert health["gpt"].model_version == "gpt-5.3-codex"
    assert health["gemini"].available is True


@pytest.mark.asyncio
async def test_health_check_partial_failure():
    """Test health check when one client fails."""
    pool = ClientPool()

    mock_gpt = AsyncMock()
    mock_gpt.analyze.return_value = {
        "analysis": "OK",
        "conclusion": "OK",
        "confidence": 0.9
    }
    pool._clients["gpt"] = mock_gpt
    pool._auth_status["gpt"] = True

    mock_gemini = AsyncMock()
    mock_gemini.analyze.side_effect = ConnectionError("API down")
    pool._clients["gemini"] = mock_gemini
    pool._auth_status["gemini"] = True

    health = await pool.health_check(timeout=10.0)

    assert health["gpt"].available is True
    assert health["gemini"].available is False
    assert "API down" in health["gemini"].error
