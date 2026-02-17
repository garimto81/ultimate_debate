"""E2E workflow verification for Ultimate Debate.

GPT/Gemini mock 클라이언트를 사용하여 전체 5-Phase 워크플로우를 검증.
- Phase 1: Parallel Analysis (Claude + GPT + Gemini)
- Phase 2: Consensus Check
- Phase 3: Cross Review (partial consensus 시)
- Phase 4: Debate Round (no consensus 시)
- Phase 5: Final Strategy + FINAL.md 생성

파일 출력 검증:
- TASK.md, round_00/{claude,gpt,gemini}.md
- CONSENSUS.md, reviews/, debates/
- FINAL.md
"""

import shutil
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ultimate_debate.engine import UltimateDebate


def _make_mock_gpt(conclusion: str = "Use Redis for distributed caching") -> AsyncMock:
    """GPT mock 클라이언트 생성."""
    mock = AsyncMock()
    mock.model_name = "gpt-5.2-codex"

    mock.analyze.return_value = {
        "analysis": "Redis는 인메모리 캐싱으로 높은 처리량과 낮은 지연시간을 제공합니다.",
        "conclusion": conclusion,
        "confidence": 0.88,
        "key_points": ["인메모리 저장", "클러스터 지원", "Pub/Sub 기능"],
        "model_version": "gpt-5.2-codex-20260201",
    }

    mock.review.return_value = {
        "feedback": "Claude의 분석에 대체로 동의합니다.",
        "agreement_points": ["Redis 선택에 동의", "클러스터 구성 권장에 동의"],
        "disagreement_points": ["Memcached도 특정 사례에서 유효"],
    }

    mock.debate.return_value = {
        "updated_position": "Redis를 기본 전략으로 채택하되, 단순 캐시에는 Memcached 병행",
        "rebuttals": ["순수 KV 캐시에서 Memcached가 더 효율적"],
        "concessions": ["복잡한 데이터 구조에는 Redis가 적합"],
    }

    return mock


def _make_mock_gemini(conclusion: str = "Use Redis for distributed caching") -> AsyncMock:
    """Gemini mock 클라이언트 생성."""
    mock = AsyncMock()
    mock.model_name = "gemini-2.5-flash"

    mock.analyze.return_value = {
        "analysis": "Redis는 다양한 데이터 구조를 지원하며 복제/클러스터링이 가능합니다.",
        "conclusion": conclusion,
        "confidence": 0.85,
        "key_points": ["다양한 데이터 타입", "AOF/RDB 영속성", "Sentinel 고가용성"],
        "model_version": "gemini-2.5-flash-001",
    }

    mock.review.return_value = {
        "feedback": "전반적으로 합리적인 분석입니다.",
        "agreement_points": ["캐싱 전략의 필요성 동의", "Redis 기본 채택 동의"],
        "disagreement_points": [],
    }

    mock.debate.return_value = {
        "updated_position": "Redis Cluster를 기본 전략으로 확정",
        "rebuttals": [],
        "concessions": ["Memcached 병행 전략에 수용"],
    }

    return mock


@pytest.fixture
def cleanup_debates():
    """테스트 후 생성된 debate 디렉토리 정리."""
    created_dirs = []
    yield created_dirs
    for d in created_dirs:
        if Path(d).exists():
            shutil.rmtree(d)


# ===== Phase 1-5: Full Consensus Scenario =====

@pytest.mark.asyncio
async def test_full_workflow_full_consensus(cleanup_debates):
    """전체 워크플로우: 3AI 모두 동일 결론 → FULL_CONSENSUS → 즉시 종료."""
    same_conclusion = "Use Redis for distributed caching"

    debate = UltimateDebate(
        task="캐싱 전략 분석: Redis vs Memcached",
        max_rounds=3,
        consensus_threshold=0.8,
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    # Claude 자체 분석 (동일 결론)
    debate.set_claude_analysis({
        "analysis": "Redis의 데이터 구조 다양성과 영속성이 장점입니다.",
        "conclusion": same_conclusion,
        "confidence": 0.9,
        "key_points": ["데이터 구조 다양성", "영속성 옵션", "Lua 스크립팅"],
    })

    # GPT/Gemini mock (동일 결론)
    debate.register_ai_client("gpt", _make_mock_gpt(same_conclusion))
    debate.register_ai_client("gemini", _make_mock_gemini(same_conclusion))

    # 전체 워크플로우 실행
    result = await debate.run()

    # === 결과 검증 ===
    assert result["status"] == "FULL_CONSENSUS"
    assert result["consensus_percentage"] == 1.0
    assert result["total_rounds"] == 0  # 첫 라운드에서 합의 도달

    # === 파일 출력 검증 ===
    base = debate.context_manager.base_path

    # TASK.md 존재
    assert (base / "TASK.md").exists(), "TASK.md 미생성"
    task_content = (base / "TASK.md").read_text(encoding="utf-8")
    assert "캐싱 전략 분석" in task_content

    # Round 0 분석 파일 (claude, gpt, gemini)
    round_dir = base / "round_00"
    assert round_dir.exists(), "round_00 디렉토리 미생성"

    for model in ["claude", "gpt", "gemini"]:
        model_file = round_dir / f"{model}.md"
        assert model_file.exists(), f"{model}.md 미생성"
        content = model_file.read_text(encoding="utf-8")
        assert "Analysis" in content
        assert "Conclusion" in content
        assert "Confidence" in content

    # CONSENSUS.md 존재
    consensus_file = round_dir / "CONSENSUS.md"
    assert consensus_file.exists(), "CONSENSUS.md 미생성"
    consensus_content = consensus_file.read_text(encoding="utf-8")
    assert "FULL_CONSENSUS" in consensus_content
    assert "100.0%" in consensus_content

    # FINAL.md 존재
    final_file = base / "FINAL.md"
    assert final_file.exists(), "FINAL.md 미생성"
    final_content = final_file.read_text(encoding="utf-8")
    assert "FULL_CONSENSUS" in final_content


@pytest.mark.asyncio
async def test_full_workflow_partial_consensus(cleanup_debates):
    """전체 워크플로우: 2/3 동의 → PARTIAL_CONSENSUS → Cross Review → Debate."""
    debate = UltimateDebate(
        task="API 게이트웨이 선택: Kong vs Envoy",
        max_rounds=2,
        consensus_threshold=0.8,
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    # Claude: Kong 선택
    debate.set_claude_analysis({
        "analysis": "Kong은 플러그인 생태계가 강력하고 설정이 간편합니다.",
        "conclusion": "Kong 채택 권장",
        "confidence": 0.85,
        "key_points": ["플러그인 생태계", "관리 UI", "쉬운 설정"],
    })

    # GPT: Kong 동의 (2/3 합의)
    mock_gpt = _make_mock_gpt("Kong 채택 권장")
    debate.register_ai_client("gpt", mock_gpt)

    # Gemini: Envoy 선호 (불일치)
    mock_gemini = _make_mock_gemini("Envoy 채택 권장")
    debate.register_ai_client("gemini", mock_gemini)

    result = await debate.run()

    # === 결과 검증 ===
    assert result["status"] in ["PARTIAL_CONSENSUS", "NO_CONSENSUS", "FULL_CONSENSUS"]
    assert result["total_rounds"] <= 2

    # === 파일 구조 검증 ===
    base = debate.context_manager.base_path

    assert (base / "TASK.md").exists()
    assert (base / "FINAL.md").exists()

    # Round 0 존재
    round_0 = base / "round_00"
    assert round_0.exists()

    # 3AI 분석 파일 모두 존재
    for model in ["claude", "gpt", "gemini"]:
        assert (round_0 / f"{model}.md").exists(), f"round_00/{model}.md 미생성"

    # Consensus 파일
    assert (round_0 / "CONSENSUS.md").exists()
    consensus_content = (round_0 / "CONSENSUS.md").read_text(encoding="utf-8")
    assert "PARTIAL_CONSENSUS" in consensus_content


@pytest.mark.asyncio
async def test_full_workflow_no_consensus(cleanup_debates):
    """전체 워크플로우: 3AI 모두 다른 결론 → NO_CONSENSUS → Debate 진입."""
    debate = UltimateDebate(
        task="프로그래밍 언어 선택: Rust vs Go vs Python",
        max_rounds=2,
        consensus_threshold=0.8,
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    # 각각 다른 결론
    debate.set_claude_analysis({
        "analysis": "Rust는 메모리 안전성과 성능이 뛰어납니다.",
        "conclusion": "Rust 채택",
        "confidence": 0.8,
        "key_points": ["메모리 안전성", "제로 코스트 추상화"],
    })

    mock_gpt = _make_mock_gpt("Go 채택")
    debate.register_ai_client("gpt", mock_gpt)

    mock_gemini = _make_mock_gemini("Python 채택")
    debate.register_ai_client("gemini", mock_gemini)

    result = await debate.run()

    # === 결과 검증 ===
    assert result["status"] in ["NO_CONSENSUS", "PARTIAL_CONSENSUS", "FULL_CONSENSUS"]
    assert result["total_rounds"] <= 2

    # === 파일 구조 검증 ===
    base = debate.context_manager.base_path

    assert (base / "TASK.md").exists()
    assert (base / "FINAL.md").exists()

    round_0 = base / "round_00"
    assert round_0.exists()

    # 3AI 분석 파일 모두 존재
    for model in ["claude", "gpt", "gemini"]:
        assert (round_0 / f"{model}.md").exists()

    # NO_CONSENSUS일 때 DEBATE next_action
    consensus_content = (round_0 / "CONSENSUS.md").read_text(encoding="utf-8")
    assert "NO_CONSENSUS" in consensus_content


# ===== 개별 Phase 검증 =====

@pytest.mark.asyncio
async def test_phase1_parallel_analysis_3ai(cleanup_debates):
    """Phase 1: 3AI 병렬 분석 - Claude + GPT + Gemini 분석 결과 및 파일 생성."""
    debate = UltimateDebate(
        task="마이크로서비스 아키텍처 리뷰",
        max_rounds=1,
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    debate.set_claude_analysis({
        "analysis": "이벤트 드리븐 아키텍처가 적합합니다.",
        "conclusion": "EDA 채택",
        "confidence": 0.87,
        "key_points": ["비동기 통신", "느슨한 결합", "확장성"],
    })

    mock_gpt = _make_mock_gpt("EDA 채택")
    mock_gemini = _make_mock_gemini("EDA 채택")
    debate.register_ai_client("gpt", mock_gpt)
    debate.register_ai_client("gemini", mock_gemini)

    analyses = await debate.run_parallel_analysis()

    # 3AI 모두 분석 완료
    assert len(analyses) == 3
    assert set(analyses.keys()) == {"claude", "gpt", "gemini"}

    # 각 분석에 필수 필드 존재
    for model, analysis in analyses.items():
        assert "analysis" in analysis
        assert "conclusion" in analysis
        assert "confidence" in analysis

    # GPT/Gemini API 호출 확인
    mock_gpt.analyze.assert_awaited_once()
    mock_gemini.analyze.assert_awaited_once()

    # 모델 버전 보존 확인
    assert analyses["gpt"]["model_version"] == "gpt-5.2-codex-20260201"
    assert analyses["gemini"]["model_version"] == "gemini-2.5-flash-001"
    assert analyses["claude"]["model_version"] == "claude-code-self"

    # 파일 출력 확인
    round_dir = debate.context_manager.base_path / "round_00"
    for model in ["claude", "gpt", "gemini"]:
        assert (round_dir / f"{model}.md").exists()


@pytest.mark.asyncio
async def test_phase2_consensus_check_varied():
    """Phase 2: 다양한 합의 시나리오 테스트."""
    from ultimate_debate.consensus.protocol import ConsensusChecker

    checker = ConsensusChecker(threshold=0.8)

    # Scenario 1: 3/3 동의 = FULL_CONSENSUS
    result = checker.check_consensus([
        {"model": "claude", "conclusion": "Redis"},
        {"model": "gpt", "conclusion": "Redis"},
        {"model": "gemini", "conclusion": "Redis"},
    ])
    assert result.status == "FULL_CONSENSUS"
    assert result.consensus_percentage == 1.0
    assert result.next_action is None

    # Scenario 2: 2/3 동의 = PARTIAL_CONSENSUS
    result = checker.check_consensus([
        {"model": "claude", "conclusion": "Redis"},
        {"model": "gpt", "conclusion": "Redis"},
        {"model": "gemini", "conclusion": "Memcached"},
    ])
    assert result.status == "PARTIAL_CONSENSUS"
    assert result.consensus_percentage == pytest.approx(2/3)
    assert result.next_action == "CROSS_REVIEW"

    # Scenario 3: 1/3 각각 다름 = NO_CONSENSUS
    result = checker.check_consensus([
        {"model": "claude", "conclusion": "Redis"},
        {"model": "gpt", "conclusion": "Memcached"},
        {"model": "gemini", "conclusion": "Hazelcast"},
    ])
    assert result.status == "NO_CONSENSUS"
    assert result.consensus_percentage == pytest.approx(1/3)
    assert result.next_action == "DEBATE"


@pytest.mark.asyncio
async def test_phase3_cross_review(cleanup_debates):
    """Phase 3: Cross Review - 외부 AI가 상호 리뷰."""
    debate = UltimateDebate(
        task="Cross Review 테스트",
        max_rounds=1,
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    debate.set_claude_analysis({
        "analysis": "Test Claude",
        "conclusion": "Claude Result",
        "confidence": 0.9,
    })

    mock_gpt = _make_mock_gpt("GPT Result")
    mock_gemini = _make_mock_gemini("Gemini Result")
    debate.register_ai_client("gpt", mock_gpt)
    debate.register_ai_client("gemini", mock_gemini)

    # Phase 1 먼저 실행 (current_analyses 설정)
    await debate.run_parallel_analysis()

    # Phase 3: Cross Review 실행
    reviews = await debate.run_cross_review()

    # 외부 AI끼리 + 외부 AI→Claude 리뷰 존재
    assert len(reviews) > 0

    # GPT가 Gemini 리뷰 / GPT가 Claude 리뷰
    assert "gpt_reviews_gemini" in reviews or "gpt_reviews_claude" in reviews

    # review API 호출 확인 (GPT가 다른 2개 모델 리뷰)
    assert mock_gpt.review.await_count == 2  # gemini + claude

    # 리뷰 파일 생성 확인
    review_dir = debate.context_manager.base_path / "round_00" / "reviews"
    assert review_dir.exists()


@pytest.mark.asyncio
async def test_phase4_debate_round(cleanup_debates):
    """Phase 4: Debate Round - 반박/양보 기반 토론."""
    debate = UltimateDebate(
        task="Debate Round 테스트",
        max_rounds=1,
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    debate.set_claude_analysis({
        "analysis": "Test Claude",
        "conclusion": "Claude Position",
        "confidence": 0.9,
    })

    mock_gpt = _make_mock_gpt("GPT Position")
    mock_gemini = _make_mock_gemini("Gemini Position")
    debate.register_ai_client("gpt", mock_gpt)
    debate.register_ai_client("gemini", mock_gemini)

    # Phase 1 먼저 실행
    await debate.run_parallel_analysis()

    # Phase 4: Debate
    debates = await debate.run_debate_round()

    # 3AI 모두 토론 참여
    assert "gpt" in debates
    assert "gemini" in debates
    assert "claude" in debates

    # GPT debate API 호출 확인
    mock_gpt.debate.assert_awaited_once()
    mock_gemini.debate.assert_awaited_once()

    # 토론 결과 구조 확인
    for model, result in debates.items():
        assert "updated_position" in result or "requires_input" in result

    # 토론 파일 생성 확인
    debate_dir = debate.context_manager.base_path / "round_00" / "debates"
    assert debate_dir.exists()
    assert (debate_dir / "gpt.md").exists()
    assert (debate_dir / "gemini.md").exists()
    assert (debate_dir / "claude.md").exists()


@pytest.mark.asyncio
async def test_phase5_final_strategy(cleanup_debates):
    """Phase 5: Final Strategy - FINAL.md 생성 및 내용 검증."""
    debate = UltimateDebate(
        task="최종 전략 테스트",
        max_rounds=1,
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    # 동일 결론으로 FULL_CONSENSUS 유도
    same_conclusion = "Final Strategy Confirmed"
    debate.set_claude_analysis({
        "analysis": "Final test",
        "conclusion": same_conclusion,
        "confidence": 0.95,
    })

    debate.register_ai_client("gpt", _make_mock_gpt(same_conclusion))
    debate.register_ai_client("gemini", _make_mock_gemini(same_conclusion))

    result = await debate.run()

    # FINAL.md 검증
    final_path = debate.context_manager.base_path / "FINAL.md"
    assert final_path.exists()
    final_content = final_path.read_text(encoding="utf-8")
    assert "FULL_CONSENSUS" in final_content
    assert "100.0%" in final_content
    assert debate.task_id in final_content


# ===== 에러 시나리오 =====

@pytest.mark.asyncio
async def test_graceful_client_failure(cleanup_debates):
    """외부 AI 1개 실패 시 graceful skip 후 나머지로 진행."""
    debate = UltimateDebate(
        task="클라이언트 실패 테스트",
        max_rounds=1,
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    debate.set_claude_analysis({
        "analysis": "Test",
        "conclusion": "OK",
        "confidence": 0.9,
    })

    # GPT: 정상
    mock_gpt = _make_mock_gpt("OK")
    debate.register_ai_client("gpt", mock_gpt)

    # Gemini: analyze 실패
    mock_gemini = AsyncMock()
    mock_gemini.analyze.side_effect = ConnectionError("API 연결 실패")
    debate.register_ai_client("gemini", mock_gemini)

    analyses = await debate.run_parallel_analysis()

    # Gemini 실패, Claude + GPT만 분석 완료
    assert "claude" in analyses
    assert "gpt" in analyses
    assert "gemini" not in analyses  # graceful skip


@pytest.mark.asyncio
async def test_model_version_preserved_in_files(cleanup_debates):
    """API 응답의 model_version이 파일에 정확히 보존되는지 확인."""
    debate = UltimateDebate(
        task="모델 버전 파일 보존 테스트",
        max_rounds=1,
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    debate.set_claude_analysis({
        "analysis": "Version test",
        "conclusion": "OK",
        "confidence": 0.9,
    })

    mock_gpt = AsyncMock()
    mock_gpt.analyze.return_value = {
        "analysis": "Version test from GPT",
        "conclusion": "OK",
        "confidence": 0.88,
        "model_version": "gpt-5.2-codex-20260201",
    }
    debate.register_ai_client("gpt", mock_gpt)

    await debate.run_parallel_analysis()

    # GPT 파일에서 model_version 확인
    gpt_file = debate.context_manager.base_path / "round_00" / "gpt.md"
    assert gpt_file.exists()
    gpt_content = gpt_file.read_text(encoding="utf-8")
    assert "gpt-5.2-codex-20260201" in gpt_content

    # Claude 파일에서 model_version 확인
    claude_file = debate.context_manager.base_path / "round_00" / "claude.md"
    assert claude_file.exists()
    claude_content = claude_file.read_text(encoding="utf-8")
    assert "claude-code-self" in claude_content


@pytest.mark.asyncio
async def test_file_structure_complete(cleanup_debates):
    """전체 워크플로우 후 파일 구조 완전성 검증."""
    debate = UltimateDebate(
        task="파일 구조 검증",
        max_rounds=1,
        consensus_threshold=0.8,
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    same = "Agreed conclusion"
    debate.set_claude_analysis({
        "analysis": "Test",
        "conclusion": same,
        "confidence": 0.9,
    })
    debate.register_ai_client("gpt", _make_mock_gpt(same))
    debate.register_ai_client("gemini", _make_mock_gemini(same))

    await debate.run()

    base = debate.context_manager.base_path

    # 전체 파일 구조
    expected_files = [
        base / "TASK.md",
        base / "FINAL.md",
        base / "round_00" / "claude.md",
        base / "round_00" / "gpt.md",
        base / "round_00" / "gemini.md",
        base / "round_00" / "CONSENSUS.md",
    ]

    for f in expected_files:
        assert f.exists(), f"Expected file missing: {f}"


@pytest.mark.asyncio
async def test_status_reflects_3ai(cleanup_debates):
    """get_status()가 3AI 참여를 정확히 반영."""
    debate = UltimateDebate(
        task="Status 테스트",
        include_claude_self=True,
    )
    cleanup_debates.append(str(debate.context_manager.base_path))

    debate.register_ai_client("gpt", _make_mock_gpt())
    debate.register_ai_client("gemini", _make_mock_gemini())

    status = debate.get_status()

    assert status["include_claude_self"] is True
    assert set(status["registered_models"]) == {"gpt", "gemini"}
    assert "claude (self)" in status["participating_models"]
    assert "gpt" in status["participating_models"]
    assert "gemini" in status["participating_models"]
    assert len(status["participating_models"]) == 3
