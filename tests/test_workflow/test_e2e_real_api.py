"""E2E test - Real API calls to GPT and Gemini through workflow.

WARNING: This test makes REAL API calls. Run manually as a script, not via pytest.
Requires valid OAuth tokens for both OpenAI and Google.

Usage:
    python tests/test_workflow/test_e2e_real_api.py
"""

import asyncio
import json
import logging
import sys
import time

import pytest

# Windows cp949 인코딩 에러 방지
sys.stdout.reconfigure(errors="replace")

# Prevent pytest from collecting E2E tests (they require real API tokens)
pytestmark = pytest.mark.skip(reason="E2E test - run manually with: python tests/test_workflow/test_e2e_real_api.py")

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
logger = logging.getLogger("e2e_test")

# ─── Color helpers ───────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")


def ok(msg: str) -> None:
    print(f"  {GREEN}[PASS]{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}[FAIL]{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {YELLOW}[INFO]{RESET} {msg}")


# ─── Tests ───────────────────────────────────────────────────────
async def test_1_client_pool_real_auth():
    """Test 1: ClientPool real authentication."""
    section("Test 1: ClientPool - Real Authentication")

    from ultimate_debate.workflow.client_pool import ClientPool

    pool = ClientPool()
    start = time.time()
    await pool.initialize()
    elapsed = time.time() - start

    results = {"gpt": False, "gemini": False}

    if "gpt" in pool.available_models:
        ok(f"GPT authenticated ({elapsed:.1f}s)")
        results["gpt"] = True
    else:
        fail("GPT authentication failed")

    if "gemini" in pool.available_models:
        ok(f"Gemini authenticated ({elapsed:.1f}s)")
        results["gemini"] = True
    else:
        fail("Gemini authentication failed")

    info(f"Available models: {pool.available_models}")

    await pool.close()
    return results


async def test_2_gpt_analyze(pool_results: dict):
    """Test 2: GPT analyze() - real API call."""
    section("Test 2: GPT analyze() - Real API Call")

    if not pool_results.get("gpt"):
        info("SKIP - GPT not authenticated")
        return None

    from ultimate_debate.clients.openai_client import OpenAIClient

    client = OpenAIClient("gpt-5.2-codex")
    await client.ensure_authenticated()

    try:
        start = time.time()
        result = await client.analyze(
            task="Python의 async/await 패턴과 threading의 차이점을 간단히 분석하세요.",
            context={"scope": "technical_comparison"},
        )
        elapsed = time.time() - start
    except Exception as e:
        fail(f"GPT API call failed: {e}")
        return None

    # Validate response structure
    passed = True

    if "analysis" in result and result["analysis"]:
        ok(f"analysis field present ({len(result['analysis'])} chars)")
    else:
        fail("analysis field missing or empty")
        passed = False

    if "conclusion" in result:
        ok(f"conclusion: {result['conclusion'][:80]}...")
    else:
        fail("conclusion field missing")
        passed = False

    if "confidence" in result:
        conf = result["confidence"]
        if isinstance(conf, (int, float)) and 0 <= conf <= 1:
            ok(f"confidence: {conf}")
        else:
            fail(f"confidence out of range: {conf}")
            passed = False
    else:
        fail("confidence field missing")
        passed = False

    info(f"Response time: {elapsed:.1f}s")
    return result if passed else None


async def test_3_gemini_analyze(pool_results: dict):
    """Test 3: Gemini analyze() - real API call."""
    section("Test 3: Gemini analyze() - Real API Call")

    if not pool_results.get("gemini"):
        info("SKIP - Gemini not authenticated")
        return None

    from ultimate_debate.clients.gemini_client import GeminiClient

    client = GeminiClient("gemini-2.5-flash")
    await client.ensure_authenticated()

    try:
        start = time.time()
        result = await client.analyze(
            task="Python의 async/await 패턴과 threading의 차이점을 간단히 분석하세요.",
            context={"scope": "technical_comparison"},
        )
        elapsed = time.time() - start
    except Exception as e:
        fail(f"Gemini API call failed: {e}")
        return None

    passed = True

    if "analysis" in result and result["analysis"]:
        ok(f"analysis field present ({len(result['analysis'])} chars)")
    else:
        fail("analysis field missing or empty")
        passed = False

    if "conclusion" in result:
        ok(f"conclusion: {result['conclusion'][:80]}...")
    else:
        fail("conclusion field missing")
        passed = False

    if "confidence" in result:
        conf = result["confidence"]
        if isinstance(conf, (int, float)):
            ok(f"confidence: {conf}")
        else:
            fail(f"confidence invalid type: {type(conf)}")
            passed = False

    info(f"Response time: {elapsed:.1f}s")
    return result if passed else None


async def test_4_phase_advisor_analyze_codebase(pool_results: dict):
    """Test 4: PhaseAdvisor.analyze_codebase() - Phase 1.0."""
    section("Test 4: PhaseAdvisor.analyze_codebase() - Phase 1.0")

    if not pool_results.get("gemini"):
        info("SKIP - Gemini not authenticated (Phase 1.0 requires Gemini)")
        return None

    from ultimate_debate.workflow.client_pool import ClientPool
    from ultimate_debate.workflow.phase_advisor import PhaseAdvisor

    pool = ClientPool()
    await pool.initialize(models=["gemini"])
    advisor = PhaseAdvisor(pool)

    try:
        start = time.time()
        result = await advisor.analyze_codebase(
            task="ultimate-debate 프로젝트의 워크플로우 모듈 구조 분석",
            file_list=[
                "src/ultimate_debate/workflow/__init__.py",
                "src/ultimate_debate/workflow/client_pool.py",
                "src/ultimate_debate/workflow/phase_advisor.py",
            ],
        )
        elapsed = time.time() - start
    except Exception as e:
        fail(f"Phase 1.0 API call failed: {e}")
        await pool.close()
        return None

    if result.get("skipped"):
        fail(f"Skipped: {result.get('reason')}")
        await pool.close()
        return None

    ok(f"Gemini codebase analysis completed ({elapsed:.1f}s)")

    if "analysis" in result:
        ok(f"analysis: {result['analysis'][:100]}...")
    else:
        fail("analysis field missing")

    await pool.close()
    return result


async def test_5_phase_advisor_review_plan(pool_results: dict):
    """Test 5: PhaseAdvisor.review_plan() - Phase 1.2."""
    section("Test 5: PhaseAdvisor.review_plan() - Phase 1.2")

    if not pool_results.get("gpt"):
        info("SKIP - GPT not authenticated (Phase 1.2 requires GPT)")
        return None

    from ultimate_debate.workflow.client_pool import ClientPool
    from ultimate_debate.workflow.phase_advisor import PhaseAdvisor

    pool = ClientPool()
    await pool.initialize(models=["gpt"])
    advisor = PhaseAdvisor(pool)

    plan_content = """## LLM Workflow Integration Plan
1. ClientPool: GPT/Gemini 클라이언트 풀 관리
2. PhaseAdvisor: Phase별 GPT/Gemini 자문 어댑터
3. run_verification(): Phase 4.2 전용 축약 워크플로우
4. Graceful degradation: 인증 실패 시 자문 스킵
"""

    try:
        start = time.time()
        result = await advisor.review_plan(
            task="LLM 워크플로우 통합 계획 리뷰",
            plan_content=plan_content,
        )
        elapsed = time.time() - start
    except Exception as e:
        fail(f"Phase 1.2 API call failed: {e}")
        await pool.close()
        return None

    if result.get("skipped"):
        fail(f"Skipped: {result.get('reason')}")
        await pool.close()
        return None

    ok(f"GPT plan review completed ({elapsed:.1f}s)")

    if "feedback" in result:
        ok(f"feedback: {result['feedback'][:100]}...")
    else:
        fail("feedback field missing")

    if "agreement_points" in result:
        ok(f"agreement_points: {len(result['agreement_points'])} items")

    if "disagreement_points" in result:
        ok(f"disagreement_points: {len(result['disagreement_points'])} items")

    await pool.close()
    return result


async def test_6_run_verification_3ai(pool_results: dict):
    """Test 6: UltimateDebate.run_verification() - Phase 4.2 with REAL 3AI."""
    section("Test 6: run_verification() - 3AI Real Consensus")

    from ultimate_debate.engine import UltimateDebate
    from ultimate_debate.workflow.client_pool import ClientPool

    # Initialize real clients
    pool = ClientPool()
    models_to_init = []
    if pool_results.get("gpt"):
        models_to_init.append("gpt")
    if pool_results.get("gemini"):
        models_to_init.append("gemini")

    if not models_to_init:
        info("SKIP - No external LLM authenticated")
        return None

    await pool.initialize(models=models_to_init)

    # Create debate engine
    debate = UltimateDebate(
        task="Python 웹 프레임워크 선택: FastAPI vs Django REST Framework",
        include_claude_self=True,
        max_rounds=2,
        consensus_threshold=0.8,
    )

    # Claude self analysis
    debate.set_claude_analysis({
        "analysis": "FastAPI는 async 네이티브, 자동 OpenAPI 문서화, 타입 힌트 기반 검증을 제공. "
                    "Django REST는 성숙한 생태계, ORM 통합, 관리자 UI를 제공. "
                    "신규 마이크로서비스에는 FastAPI, 대규모 모놀리식에는 Django REST 추천.",
        "conclusion": "용도에 따라 선택: 마이크로서비스=FastAPI, 모놀리식=DRF",
        "confidence": 0.85,
        "key_points": ["FastAPI: async, 성능", "DRF: 생태계, ORM"],
    })

    # Register real clients
    gpt_client = await pool.get_client("gpt")
    if gpt_client:
        debate.register_ai_client("gpt", gpt_client)
        info("GPT registered for debate")

    gemini_client = await pool.get_client("gemini")
    if gemini_client:
        debate.register_ai_client("gemini", gemini_client)
        info("Gemini registered for debate")

    # Run verification
    try:
        start = time.time()
        result = await debate.run_verification()
        elapsed = time.time() - start
    except Exception as e:
        fail(f"run_verification failed: {e}")
        await pool.close()
        return None

    # Validate result
    ok(f"Verification completed ({elapsed:.1f}s)")

    if "status" in result:
        status = result["status"]
        ok(f"Consensus status: {status}")
    else:
        fail("status field missing")

    if "consensus_percentage" in result:
        pct = result["consensus_percentage"]
        ok(f"Consensus percentage: {pct*100:.1f}%")
    else:
        fail("consensus_percentage field missing")

    if "analyses" in result:
        analyses = result["analyses"]
        for model, conclusion in analyses.items():
            ok(f"  {model}: {str(conclusion)[:80]}...")
    else:
        fail("analyses field missing")

    if "agreed_items" in result:
        ok(f"Agreed items: {len(result['agreed_items'])}")

    if "disputed_items" in result:
        ok(f"Disputed items: {len(result['disputed_items'])}")

    await pool.close()
    return result


async def test_7_full_workflow_integration(pool_results: dict):
    """Test 7: Full PhaseAdvisor workflow (1.0 -> 1.2 -> 4.2)."""
    section("Test 7: Full Workflow Integration (Phase 1.0 -> 1.2 -> 4.2)")

    has_any = pool_results.get("gpt") or pool_results.get("gemini")
    if not has_any:
        info("SKIP - No external LLM authenticated")
        return None

    from ultimate_debate.workflow.client_pool import ClientPool
    from ultimate_debate.workflow.phase_advisor import PhaseAdvisor

    pool = ClientPool()
    await pool.initialize()
    advisor = PhaseAdvisor(pool)

    total_start = time.time()

    try:
        # Phase 1.0: Codebase analysis (Gemini)
        info("Phase 1.0: Codebase analysis...")
        p10_result = await advisor.analyze_codebase(
            task="워크플로우 통합 모듈 분석",
            file_list=["src/ultimate_debate/workflow/client_pool.py"],
        )
        if p10_result.get("skipped"):
            info(f"Phase 1.0 skipped: {p10_result.get('reason')}")
        else:
            ok(f"Phase 1.0 completed: {str(p10_result.get('conclusion', ''))[:60]}")

        # Phase 1.2: Plan review (GPT)
        info("Phase 1.2: Plan review...")
        p12_result = await advisor.review_plan(
            task="LLM 통합 계획 리뷰",
            plan_content="## Plan\n1. ClientPool 구현\n2. PhaseAdvisor 구현\n3. E2E 검증",
        )
        if p12_result.get("skipped"):
            info(f"Phase 1.2 skipped: {p12_result.get('reason')}")
        else:
            ok(f"Phase 1.2 completed: {str(p12_result.get('feedback', ''))[:60]}")

        # Phase 4.2: 3AI verification
        info("Phase 4.2: 3AI verification...")
        p42_result = await advisor.verify_implementation(
            task="워크플로우 통합 검증",
            code_summary="ClientPool + PhaseAdvisor + run_verification 구현 완료",
            claude_verdict={
                "analysis": "구현이 Plan 대로 완료됨",
                "conclusion": "APPROVE",
                "confidence": 0.9,
            },
        )
        ok(f"Phase 4.2 completed: status={p42_result.get('status')}")
    except Exception as e:
        fail(f"Full workflow failed: {e}")
        await pool.close()
        return None

    total_elapsed = time.time() - total_start
    info(f"Total workflow time: {total_elapsed:.1f}s")

    await pool.close()
    return p42_result


# ─── Main runner ─────────────────────────────────────────────────
async def main():
    """Run all E2E tests sequentially."""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Ultimate Debate - LLM Workflow E2E Verification{RESET}")
    print(f"{BOLD}  Real API calls to GPT and Gemini{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    total_start = time.time()
    results = {}

    # Test 1: Auth
    pool_results = await test_1_client_pool_real_auth()
    results["auth"] = pool_results

    # Test 2: GPT analyze
    gpt_result = await test_2_gpt_analyze(pool_results)
    results["gpt_analyze"] = gpt_result is not None

    # Test 3: Gemini analyze
    gemini_result = await test_3_gemini_analyze(pool_results)
    results["gemini_analyze"] = gemini_result is not None

    # Test 4: Phase 1.0
    p10_result = await test_4_phase_advisor_analyze_codebase(pool_results)
    results["phase_1_0"] = p10_result is not None

    # Test 5: Phase 1.2
    p12_result = await test_5_phase_advisor_review_plan(pool_results)
    results["phase_1_2"] = p12_result is not None

    # Test 6: 3AI verification
    p42_result = await test_6_run_verification_3ai(pool_results)
    results["phase_4_2"] = p42_result is not None

    # Test 7: Full workflow
    full_result = await test_7_full_workflow_integration(pool_results)
    results["full_workflow"] = full_result is not None

    total_elapsed = time.time() - total_start

    # Summary
    section("SUMMARY")
    passed = sum(1 for v in results.values() if v is True or (isinstance(v, dict) and any(v.values())))
    total = len(results)
    skipped = sum(1 for v in results.values() if v is None or v is False)

    for test_name, result in results.items():
        if isinstance(result, dict):
            status = f"{GREEN}PASS{RESET}" if any(result.values()) else f"{RED}FAIL{RESET}"
        elif result is True:
            status = f"{GREEN}PASS{RESET}"
        elif result is False:
            status = f"{RED}FAIL{RESET}"
        else:
            status = f"{YELLOW}SKIP{RESET}"
        print(f"  {status}  {test_name}")

    print(f"\n  Total: {passed} passed, {skipped} skipped/failed")
    print(f"  Time: {total_elapsed:.1f}s\n")


if __name__ == "__main__":
    asyncio.run(main())
