"""Test ultimate debate engine."""

import pytest

from ultimate_debate.engine import UltimateDebate
from ultimate_debate.consensus.protocol import ConsensusChecker


@pytest.mark.asyncio
async def test_debate_with_mock_clients():
    """Test debate engine with mock AI clients."""
    debate = UltimateDebate(
        task="Analyze the best approach for caching",
        max_rounds=2,
        consensus_threshold=0.8,
        include_claude_self=False,  # mock 모드에서는 Claude 자체 참여 비활성화
    )

    # Run without real clients (uses mock)
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
        "analysis": "REST API보다 GraphQL이 적합합니다. 유연한 쿼리와 타입 시스템 제공.",
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
    """Test consensus checker logic."""
    checker = ConsensusChecker(threshold=0.8)

    analyses = [
        {"model": "claude", "conclusion": "Use Redis for caching"},
        {"model": "gpt", "conclusion": "Use Redis for caching"},
        {"model": "gemini", "conclusion": "Use Memcached"},
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
        "analysis": "Redis 클러스터 사용 권장",
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
