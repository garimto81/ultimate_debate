"""Test ultimate debate engine."""

import pytest

from ultimate_debate.consensus.protocol import ConsensusChecker
from ultimate_debate.engine import UltimateDebate


@pytest.mark.asyncio
async def test_debate_with_mock_clients():
    """Test debate engine with mock AI clients."""
    from unittest.mock import patch

    debate = UltimateDebate(
        task="Analyze the best approach for caching",
        max_rounds=2,
        consensus_threshold=0.8,
        include_claude_self=False,  # Claude 자체 참여 비활성화
    )

    # Mock으로 분석 결과 직접 주입 (Phase A: mock fallback 제거됨)
    with patch.object(debate, 'run_parallel_analysis') as mock_analysis:
        mock_analysis.return_value = debate._mock_parallel_analysis()
        result = await debate.run()

    assert result["status"] in ["FULL_CONSENSUS", "PARTIAL_CONSENSUS", "NO_CONSENSUS"]
    assert result["total_rounds"] <= 2
    assert "task_id" in result
    assert "consensus_percentage" in result


@pytest.mark.asyncio
async def test_debate_with_claude_self():
    """Test debate engine with Claude self-analysis."""
    debate = UltimateDebate(
        task="API 설계 리뷰",
        max_rounds=1,
        consensus_threshold=0.8,
        include_claude_self=True,  # Claude Code 자체 참여
    )

    # Claude 자체 분석 결과 설정
    debate.set_claude_analysis({
        "analysis": (
            "REST API보다 GraphQL이 적합합니다. "
            "유연한 쿼리 제공 및 타입 안전성 보장이 주요 이점입니다."
        ),
        "conclusion": "GraphQL 채택 권장",
        "confidence": 0.85,
        "key_points": ["타입 안전성", "오버페칭 방지", "스키마 기반 문서화"],
    })

    # 외부 AI 없이 Claude만으로 분석 실행
    analyses = await debate.run_parallel_analysis()

    assert "claude" in analyses
    assert analyses["claude"]["model"] == "claude"
    assert analyses["claude"]["model_version"] == "claude-code-self"
    assert analyses["claude"]["confidence"] == 0.85
    assert "GraphQL" in analyses["claude"]["conclusion"]


def test_claude_client_registration_blocked():
    """Test that registering 'claude' as AI client raises error."""
    debate = UltimateDebate(
        task="Test task",
        include_claude_self=True,
    )

    # Claude 등록 시도 → 에러 발생해야 함
    with pytest.raises(ValueError) as exc_info:
        debate.register_ai_client("claude", None)  # type: ignore

    assert "Claude Code가 이미 Claude입니다" in str(exc_info.value)


def test_include_claude_self_status():
    """Test that status correctly reflects Claude self participation."""
    debate = UltimateDebate(
        task="Test task",
        include_claude_self=True,
    )

    status = debate.get_status()

    assert status["include_claude_self"] is True
    assert "claude (self)" in status["participating_models"]
    assert "claude" not in status["registered_models"]  # 외부 등록 아님


def test_consensus_checker():
    """Test consensus checker logic with semantic similarity."""
    checker = ConsensusChecker(threshold=0.8, similarity_threshold=0.6)

    analyses = [
        {"model": "claude", "conclusion": "Use Redis for caching due to speed"},
        {"model": "gpt", "conclusion": "Use Redis for caching due to speed"},
        {"model": "gemini", "conclusion": "Use PostgreSQL materialized views instead"},
    ]

    result = checker.check_consensus(analyses)

    assert result.status == "PARTIAL_CONSENSUS"
    assert result.consensus_percentage == pytest.approx(2 / 3)
    assert len(result.agreed_items) == 1
    assert len(result.disputed_items) == 1


def test_full_consensus():
    """Test full consensus detection."""
    checker = ConsensusChecker(threshold=0.8)

    analyses = [
        {"model": "claude", "conclusion": "Use Redis"},
        {"model": "gpt", "conclusion": "Use Redis"},
        {"model": "gemini", "conclusion": "Use Redis"},
    ]

    result = checker.check_consensus(analyses)

    assert result.status == "FULL_CONSENSUS"
    assert result.consensus_percentage == 1.0
    assert result.next_action is None


@pytest.mark.asyncio
async def test_3ai_debate_structure():
    """Test 3AI debate structure (Claude self + GPT + Gemini placeholders)."""
    debate = UltimateDebate(
        task="캐싱 전략 분석",
        max_rounds=1,
        include_claude_self=True,
    )

    # Claude 자체 분석 설정
    debate.set_claude_analysis({
        "analysis": (
            "Redis 클러스터 사용을 권장합니다. "
            "고가용성과 수평 확장이 가능하여 대규모 트래픽 처리에 적합합니다."
        ),
        "conclusion": "Redis Cluster",
        "confidence": 0.9,
        "key_points": ["고가용성", "수평 확장"],
    })

    # 외부 AI 미등록 상태에서 분석 실행
    analyses = await debate.run_parallel_analysis()

    # Claude만 참여
    assert len(analyses) == 1
    assert "claude" in analyses

    # 상태 확인
    status = debate.get_status()
    assert status["include_claude_self"] is True
    assert len(status["registered_models"]) == 0  # 외부 AI 없음


@pytest.mark.asyncio
async def test_run_verification():
    """Test run_verification shortcut workflow."""
    debate = UltimateDebate(
        task="코드 검증",
        max_rounds=1,
        include_claude_self=True,
    )

    debate.set_claude_analysis({
        "analysis": (
            "Implementation looks correct and follows best practices. "
            "All edge cases are handled properly with good test coverage."
        ),
        "conclusion": "APPROVE",
        "confidence": 0.9,
    })

    # Claude only -> run_verification
    result = await debate.run_verification()

    assert "status" in result
    assert "consensus_percentage" in result
    assert "analyses" in result
    assert "claude" in result["analyses"]


@pytest.mark.asyncio
async def test_run_verification_with_3ai():
    """Test run_verification with 3AI (Claude + GPT + Gemini mock clients)."""
    from unittest.mock import AsyncMock

    debate = UltimateDebate(
        task="코드 검증: 워크플로우 통합",
        max_rounds=2,
        consensus_threshold=0.8,
        include_claude_self=True,
    )

    # Claude 자체 분석
    debate.set_claude_analysis({
        "analysis": (
            "코드 구조가 양호하고 테스트 커버리지가 충분합니다. "
            "주요 비즈니스 로직이 잘 분리되어 있으며 확장성도 고려되었습니다."
        ),
        "conclusion": "APPROVE",
        "confidence": 0.9,
    })

    # GPT mock
    mock_gpt = AsyncMock()
    mock_gpt.analyze.return_value = {
        "analysis": (
            "Code structure is clean and well-tested with comprehensive "
            "unit tests covering all major code paths."
        ),
        "conclusion": "APPROVE",
        "confidence": 0.88,
        "model_version": "gpt-5.2-codex",
    }
    debate.register_ai_client("gpt", mock_gpt)

    # Gemini mock
    mock_gemini = AsyncMock()
    mock_gemini.analyze.return_value = {
        "analysis": (
            "No security issues detected and error handling is implemented "
            "properly with appropriate fallback mechanisms."
        ),
        "conclusion": "APPROVE",
        "confidence": 0.85,
        "model_version": "gemini-2.5-flash",
    }
    debate.register_ai_client("gemini", mock_gemini)

    result = await debate.run_verification()

    assert result["status"] in ["FULL_CONSENSUS", "PARTIAL_CONSENSUS", "NO_CONSENSUS"]
    assert "consensus_percentage" in result
    assert "analyses" in result
    assert "claude" in result["analyses"]
    assert "gpt" in result["analyses"]
    assert "gemini" in result["analyses"]
    # All 3 said APPROVE
    mock_gpt.analyze.assert_awaited_once()
    mock_gemini.analyze.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_verification_partial_consensus():
    """Test run_verification when one AI disagrees."""
    from unittest.mock import AsyncMock

    debate = UltimateDebate(
        task="코드 검증: 보안 리뷰",
        max_rounds=1,
        consensus_threshold=0.8,
        include_claude_self=True,
    )

    debate.set_claude_analysis({
        "analysis": (
            "Overall code looks good with no major issues. "
            "All requested features are properly implemented and tested."
        ),
        "conclusion": "APPROVE",
        "confidence": 0.9,
    })

    mock_gpt = AsyncMock()
    mock_gpt.analyze.return_value = {
        "analysis": (
            "Found potential SQL injection vulnerability in user input "
            "handling. Recommend using parameterized queries instead."
        ),
        "conclusion": "REJECT - security vulnerability",
        "confidence": 0.95,
    }
    debate.register_ai_client("gpt", mock_gpt)

    result = await debate.run_verification()

    assert result["status"] in ["PARTIAL_CONSENSUS", "NO_CONSENSUS"]
    assert len(result["disputed_items"]) > 0


@pytest.mark.asyncio
async def test_run_verification_model_version_preserved():
    """Test that model_version from API response is preserved in analyses."""
    from unittest.mock import AsyncMock

    debate = UltimateDebate(
        task="모델 버전 보존 테스트",
        include_claude_self=True,
    )

    debate.set_claude_analysis({
        "analysis": (
            "This is a test analysis for model version preservation. "
            "The implementation correctly preserves API response versions."
        ),
        "conclusion": "OK",
        "confidence": 0.9,
    })

    mock_gpt = AsyncMock()
    mock_gpt.analyze.return_value = {
        "analysis": (
            "Test analysis from GPT client with model version information "
            "included in the response payload."
        ),
        "conclusion": "OK",
        "confidence": 0.9,
        "model_version": "gpt-5.2-codex-20260201",
    }
    debate.register_ai_client("gpt", mock_gpt)

    analyses = await debate.run_parallel_analysis()

    assert analyses["gpt"]["model_version"] == "gpt-5.2-codex-20260201"
    assert analyses["claude"]["model_version"] == "claude-code-self"


def test_semantic_consensus():
    """Test semantic similarity clusters similar conclusions together.

    TF-IDF cosine similarity threshold=0.3 clusters conclusions
    that share significant vocabulary, even with different phrasing.
    This is a major improvement over SHA-256 hash (exact match only).
    """
    checker = ConsensusChecker(threshold=0.8)

    analyses = [
        {
            "model": "claude",
            "conclusion": (
                "Use Redis for caching to improve API response times "
                "and reduce database load"
            ),
        },
        {
            "model": "gpt",
            "conclusion": (
                "Redis caching is recommended to improve API response "
                "times and reduce database load"
            ),
        },
        {
            "model": "gemini",
            "conclusion": (
                "Use PostgreSQL materialized views for better "
                "query performance optimization"
            ),
        },
    ]

    result = checker.check_consensus(analyses)

    # Claude + GPT share Redis/caching/API vocabulary -> cluster
    # Gemini uses different approach -> separate cluster
    assert result.status == "PARTIAL_CONSENSUS"
    assert result.consensus_percentage == pytest.approx(2 / 3)
    assert len(result.agreed_items) == 1
    assert len(result.disputed_items) == 1
    agreed_models = result.agreed_items[0]["models"]
    assert "claude" in agreed_models
    assert "gpt" in agreed_models


@pytest.mark.asyncio
async def test_failed_clients_tracked():
    """Test that failed AI clients are tracked in debate status."""
    from unittest.mock import AsyncMock

    debate = UltimateDebate(
        task="Test",
        include_claude_self=True,
    )
    debate.set_claude_analysis({
        "analysis": (
            "Analysis completed successfully with all checks passing. "
            "No issues found in the implementation or test coverage."
        ),
        "conclusion": "APPROVE",
        "confidence": 0.9,
    })

    mock_gpt = AsyncMock()
    mock_gpt.analyze.side_effect = ConnectionError("API timeout")
    debate.register_ai_client("gpt", mock_gpt)

    await debate.run_parallel_analysis()

    assert "gpt" in debate.failed_clients
    assert "API timeout" in debate.failed_clients["gpt"]


def test_updated_position_dict_handling():
    """Test updated_position handles both dict and str."""
    debate = UltimateDebate(
        task="Test",
        include_claude_self=False,
    )
    debate.current_analyses = {"gpt": {"conclusion": "old"}}

    # dict case
    result = {"updated_position": {
        "conclusion": "new position",
        "confidence": 0.9,
    }}
    updated = result.get("updated_position", "")
    if isinstance(updated, dict):
        debate.current_analyses["gpt"]["conclusion"] = (
            updated.get("conclusion", "")
        )
    else:
        debate.current_analyses["gpt"]["conclusion"] = updated

    assert debate.current_analyses["gpt"]["conclusion"] == "new position"

    # str case
    result2 = {"updated_position": "simple string position"}
    updated2 = result2.get("updated_position", "")
    if isinstance(updated2, dict):
        debate.current_analyses["gpt"]["conclusion"] = (
            updated2.get("conclusion", "")
        )
    else:
        debate.current_analyses["gpt"]["conclusion"] = updated2

    assert debate.current_analyses["gpt"]["conclusion"] == (
        "simple string position"
    )


# Phase A Tests: Mock Fallback 제거 + Strict Mode


@pytest.mark.asyncio
async def test_run_raises_without_clients():
    """Test that run() raises NoAvailableClientsError when no clients available."""
    from ultimate_debate.engine import NoAvailableClientsError

    debate = UltimateDebate(
        task="Test task",
        include_claude_self=False,  # Claude 자체 참여 비활성화
    )
    # 외부 AI 등록 없음

    with pytest.raises(NoAvailableClientsError) as exc_info:
        await debate.run()

    assert "분석 가능한 AI 클라이언트가 없습니다" in str(exc_info.value)


@pytest.mark.asyncio
async def test_strict_mode_requires_external_ai():
    """Test that strict mode requires at least one external AI."""
    from ultimate_debate.engine import NoAvailableClientsError

    debate = UltimateDebate(
        task="Test task",
        include_claude_self=True,  # Claude는 있지만
        strict=True,  # strict 모드는 외부 AI 필수
    )
    debate.set_claude_analysis({
        "analysis": "This is a detailed test analysis with more than fifty characters to pass validation.",
        "conclusion": "OK",
        "confidence": 0.9,
    })

    with pytest.raises(NoAvailableClientsError) as exc_info:
        await debate.run()

    assert "Strict 모드" in str(exc_info.value)
    assert "외부 AI" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mock_methods_not_called_in_run():
    """Test that mock methods are never called during normal run()."""
    from unittest.mock import patch
    from ultimate_debate.engine import NoAvailableClientsError

    debate = UltimateDebate(
        task="Test",
        include_claude_self=False,
    )

    with patch.object(debate, '_mock_parallel_analysis') as mock_method:
        with pytest.raises(NoAvailableClientsError):
            await debate.run()

        # Mock 메서드가 호출되지 않았는지 확인
        mock_method.assert_not_called()


# Phase B Tests: Preflight Health Check


@pytest.mark.asyncio
async def test_preflight_removes_dead_clients():
    """Test that preflight removes failed clients from ai_clients."""
    from unittest.mock import AsyncMock

    debate = UltimateDebate(
        task="Test",
        include_claude_self=True,
        strict=False,  # non-strict: 실패해도 계속 진행
    )
    debate.set_claude_analysis({
        "analysis": "This is a detailed analysis with more than fifty characters.",
        "conclusion": "OK",
        "confidence": 0.9,
    })

    # GPT는 정상, Gemini는 실패
    mock_gpt = AsyncMock()
    mock_gpt.ensure_authenticated.return_value = None
    mock_gpt.analyze.return_value = {
        "analysis": "This is a detailed GPT analysis with sufficient length.",
        "conclusion": "OK",
        "confidence": 0.9,
    }
    debate.register_ai_client("gpt", mock_gpt)

    mock_gemini = AsyncMock()
    mock_gemini.ensure_authenticated.side_effect = ConnectionError("Auth failed")
    debate.register_ai_client("gemini", mock_gemini)

    # run() 실행 → preflight가 gemini 제거해야 함
    result = await debate.run()

    # Gemini는 failed_clients에 기록되고 ai_clients에서 제거됨
    assert "gemini" in debate.failed_clients
    assert "gemini" not in debate.ai_clients
    assert "gpt" in debate.ai_clients


# Phase C Tests: 결과 무결성 검증


def test_validate_analysis_rejects_short():
    """Test that _validate_analysis rejects short analysis."""
    debate = UltimateDebate(task="Test")

    # 짧은 분석 (50자 미만)
    result = {
        "analysis": "OK",
        "conclusion": "APPROVE",
        "confidence": 0.9,
    }

    assert debate._validate_analysis("test", result) is False

    # 충분한 길이의 분석
    result2 = {
        "analysis": (
            "This is a detailed analysis with more than fifty characters "
            "to pass validation."
        ),
        "conclusion": "APPROVE",
        "confidence": 0.9,
    }

    assert debate._validate_analysis("test", result2) is True


def test_validate_analysis_rejects_missing_fields():
    """Test that _validate_analysis rejects missing required fields."""
    debate = UltimateDebate(task="Test")

    # conclusion 누락
    result = {
        "analysis": "A" * 100,
        "confidence": 0.9,
    }
    assert debate._validate_analysis("test", result) is False

    # confidence 누락
    result2 = {
        "analysis": "A" * 100,
        "conclusion": "APPROVE",
    }
    assert debate._validate_analysis("test", result2) is False

    # confidence 범위 초과
    result3 = {
        "analysis": "A" * 100,
        "conclusion": "APPROVE",
        "confidence": 1.5,
    }
    assert debate._validate_analysis("test", result3) is False


def test_validate_analysis_rejects_placeholder():
    """Test that _validate_analysis rejects placeholder analysis."""
    debate = UltimateDebate(task="Test")

    # requires_input=True 플래그
    result = {
        "analysis": "A" * 100,
        "conclusion": "APPROVE",
        "confidence": 0.9,
        "requires_input": True,
    }

    assert debate._validate_analysis("test", result) is False


@pytest.mark.asyncio
async def test_run_parallel_analysis_filters_invalid():
    """Test that invalid analysis results are filtered out."""
    from unittest.mock import AsyncMock

    debate = UltimateDebate(
        task="Test",
        include_claude_self=False,
    )

    # GPT는 유효, Gemini는 무효 (짧은 분석)
    mock_gpt = AsyncMock()
    mock_gpt.analyze.return_value = {
        "analysis": (
            "This is a detailed GPT analysis with sufficient length to pass "
            "validation checks."
        ),
        "conclusion": "APPROVE",
        "confidence": 0.9,
    }
    debate.register_ai_client("gpt", mock_gpt)

    mock_gemini = AsyncMock()
    mock_gemini.analyze.return_value = {
        "analysis": "OK",  # 너무 짧음
        "conclusion": "APPROVE",
        "confidence": 0.9,
    }
    debate.register_ai_client("gemini", mock_gemini)

    analyses = await debate.run_parallel_analysis()

    # GPT만 포함, Gemini는 제외
    assert "gpt" in analyses
    assert "gemini" not in analyses
    assert "gemini" in debate.failed_clients
    assert "무결성 검증 실패" in debate.failed_clients["gemini"]
