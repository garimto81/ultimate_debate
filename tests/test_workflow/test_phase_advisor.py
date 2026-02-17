"""Test PhaseAdvisor - auxiliary LLM advisory for PDCA phases."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ultimate_debate.workflow.client_pool import ClientPool
from ultimate_debate.workflow.phase_advisor import PhaseAdvisor


def _make_pool_with_clients(gpt=None, gemini=None):
    """Create a mock ClientPool with optional clients."""
    pool = MagicMock(spec=ClientPool)

    async def mock_get_client(model: str):
        if model == "gpt":
            return gpt
        if model == "gemini":
            return gemini
        return None

    pool.get_client = AsyncMock(side_effect=mock_get_client)
    pool.available_models = []
    if gpt:
        pool.available_models.append("gpt")
    if gemini:
        pool.available_models.append("gemini")
    return pool


@pytest.mark.asyncio
async def test_analyze_codebase_with_gemini():
    """Phase 1.0: Gemini analyzes codebase successfully."""
    mock_gemini = AsyncMock()
    mock_gemini.analyze.return_value = {
        "analysis": "Large codebase with modular structure",
        "conclusion": "Well organized",
        "confidence": 0.8,
    }

    pool = _make_pool_with_clients(gemini=mock_gemini)
    advisor = PhaseAdvisor(pool)

    result = await advisor.analyze_codebase(
        task="Analyze project structure",
        file_list=["src/main.py", "src/utils.py"],
    )

    assert result["analysis"] == "Large codebase with modular structure"
    assert "skipped" not in result
    mock_gemini.analyze.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_codebase_without_gemini():
    """Phase 1.0: Gemini unavailable -> skipped gracefully."""
    pool = _make_pool_with_clients()  # no clients
    advisor = PhaseAdvisor(pool)

    result = await advisor.analyze_codebase(
        task="Analyze project structure",
        file_list=["src/main.py"],
    )

    assert result["skipped"] is True
    assert "reason" in result


@pytest.mark.asyncio
async def test_review_plan_with_gpt():
    """Phase 1.2: GPT reviews plan successfully."""
    mock_gpt = AsyncMock()
    mock_gpt.review.return_value = {
        "feedback": "Plan is comprehensive but missing error handling",
        "agreement_points": ["Good architecture", "Clear scope"],
        "disagreement_points": ["Missing rollback strategy"],
    }

    pool = _make_pool_with_clients(gpt=mock_gpt)
    advisor = PhaseAdvisor(pool)

    result = await advisor.review_plan(
        task="Implement caching layer",
        plan_content="## Plan\n1. Add Redis...",
    )

    assert "feedback" in result
    assert len(result["disagreement_points"]) == 1
    assert "skipped" not in result


@pytest.mark.asyncio
async def test_review_plan_without_gpt():
    """Phase 1.2: GPT unavailable -> skipped gracefully."""
    pool = _make_pool_with_clients()
    advisor = PhaseAdvisor(pool)

    result = await advisor.review_plan(
        task="Implement caching layer",
        plan_content="## Plan\n1. Add Redis...",
    )

    assert result["skipped"] is True


@pytest.mark.asyncio
async def test_verify_implementation_3ai():
    """Phase 4.2: Full 3AI verification with consensus."""
    mock_gpt = AsyncMock()
    mock_gpt.analyze.return_value = {
        "analysis": "Code looks correct",
        "conclusion": "APPROVE",
        "confidence": 0.9,
    }

    mock_gemini = AsyncMock()
    mock_gemini.analyze.return_value = {
        "analysis": "No issues found",
        "conclusion": "APPROVE",
        "confidence": 0.85,
    }

    pool = _make_pool_with_clients(gpt=mock_gpt, gemini=mock_gemini)
    advisor = PhaseAdvisor(pool)

    claude_verdict = {
        "analysis": "Implementation follows design spec",
        "conclusion": "APPROVE",
        "confidence": 0.9,
        "key_points": ["TDD compliant", "Error handling present"],
    }

    result = await advisor.verify_implementation(
        task="Verify caching implementation",
        code_summary="Added Redis caching with TTL",
        claude_verdict=claude_verdict,
    )

    assert "status" in result
    assert "consensus_percentage" in result
    assert "analyses" in result


@pytest.mark.asyncio
async def test_verify_implementation_no_external_llm():
    """Phase 4.2: No external LLM -> Claude-only verification."""
    pool = _make_pool_with_clients()  # no clients
    advisor = PhaseAdvisor(pool)

    claude_verdict = {
        "analysis": "Implementation follows design spec",
        "conclusion": "APPROVE",
        "confidence": 0.9,
    }

    result = await advisor.verify_implementation(
        task="Verify caching implementation",
        code_summary="Added Redis caching with TTL",
        claude_verdict=claude_verdict,
    )

    # Claude-only: single analysis -> NO_CONSENSUS due to < 2 analyses
    assert "status" in result


@pytest.mark.asyncio
async def test_verify_implementation_partial_llm():
    """Phase 4.2: Only GPT available -> 2AI verification."""
    mock_gpt = AsyncMock()
    mock_gpt.analyze.return_value = {
        "analysis": "Looks good",
        "conclusion": "APPROVE",
        "confidence": 0.85,
    }

    pool = _make_pool_with_clients(gpt=mock_gpt)
    advisor = PhaseAdvisor(pool)

    claude_verdict = {
        "analysis": "Good implementation",
        "conclusion": "APPROVE",
        "confidence": 0.9,
    }

    result = await advisor.verify_implementation(
        task="Verify implementation",
        code_summary="New feature added",
        claude_verdict=claude_verdict,
    )

    assert "status" in result
    assert "consensus_percentage" in result


@pytest.mark.asyncio
async def test_summarize_results_with_gemini():
    """Phase 5: Gemini summarizes PDCA results."""
    mock_gemini = AsyncMock()
    mock_gemini.analyze.return_value = {
        "analysis": "PDCA cycle completed successfully with 3 changes",
        "conclusion": "All phases passed",
        "confidence": 0.9,
    }

    pool = _make_pool_with_clients(gemini=mock_gemini)
    advisor = PhaseAdvisor(pool)

    result = await advisor.summarize_results(
        task="Summarize PDCA cycle",
        results={"phases": {"plan": "done", "do": "done", "check": "passed"}},
    )

    assert "analysis" in result
    assert "skipped" not in result


@pytest.mark.asyncio
async def test_summarize_results_without_gemini():
    """Phase 5: Gemini unavailable -> skipped gracefully."""
    pool = _make_pool_with_clients()
    advisor = PhaseAdvisor(pool)

    result = await advisor.summarize_results(
        task="Summarize PDCA cycle",
        results={},
    )

    assert result["skipped"] is True


@pytest.mark.asyncio
async def test_verify_implementation_api_error_graceful():
    """Phase 4.2: API error during verification -> graceful handling."""
    mock_gpt = AsyncMock()
    mock_gpt.analyze.side_effect = Exception("API timeout")

    mock_gemini = AsyncMock()
    mock_gemini.analyze.return_value = {
        "analysis": "Looks good",
        "conclusion": "APPROVE",
        "confidence": 0.8,
    }

    pool = _make_pool_with_clients(gpt=mock_gpt, gemini=mock_gemini)
    advisor = PhaseAdvisor(pool)

    claude_verdict = {
        "analysis": "Good",
        "conclusion": "APPROVE",
        "confidence": 0.9,
    }

    # Should not crash even if GPT fails mid-verification
    result = await advisor.verify_implementation(
        task="Verify implementation",
        code_summary="New feature",
        claude_verdict=claude_verdict,
    )

    assert "status" in result


@pytest.mark.asyncio
async def test_full_pdca_advisory_flow():
    """Test complete PDCA advisory flow: Phase 1.0 -> 1.2 -> 4.2 -> 5."""
    mock_gpt = AsyncMock()
    mock_gpt.analyze.return_value = {
        "analysis": "Good structure",
        "conclusion": "APPROVE",
        "confidence": 0.88,
        "model_version": "gpt-5.2-codex",
    }
    mock_gpt.review.return_value = {
        "feedback": "Plan is solid",
        "agreement_points": ["Good scope"],
        "disagreement_points": [],
    }

    mock_gemini = AsyncMock()
    mock_gemini.analyze.return_value = {
        "analysis": "Well organized codebase",
        "conclusion": "APPROVE",
        "confidence": 0.85,
        "model_version": "gemini-2.5-flash",
    }

    pool = _make_pool_with_clients(gpt=mock_gpt, gemini=mock_gemini)
    advisor = PhaseAdvisor(pool)

    # Phase 1.0: Codebase analysis (Gemini)
    codebase_result = await advisor.analyze_codebase(
        task="Analyze project",
        file_list=["src/engine.py", "src/workflow/"],
    )
    assert "skipped" not in codebase_result

    # Phase 1.2: Plan review (GPT)
    plan_result = await advisor.review_plan(
        task="Implement caching",
        plan_content="## Plan\n1. Add Redis\n2. TTL config",
    )
    assert len(plan_result["disagreement_points"]) == 0

    # Phase 4.2: 3AI verification
    verify_result = await advisor.verify_implementation(
        task="Verify caching",
        code_summary="Redis caching with TTL",
        claude_verdict={
            "analysis": "Implementation correct",
            "conclusion": "APPROVE",
            "confidence": 0.9,
        },
    )
    assert "status" in verify_result

    # Phase 5: Summarize (Gemini)
    summary_result = await advisor.summarize_results(
        task="PDCA summary",
        results={"plan": "done", "do": "done", "check": "passed"},
    )
    assert "skipped" not in summary_result

    # Verify call counts
    assert mock_gemini.analyze.await_count >= 2  # Phase 1.0 + Phase 4.2 + Phase 5
    assert mock_gpt.review.await_count == 1  # Phase 1.2
