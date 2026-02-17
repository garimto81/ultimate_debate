"""실제 GPT/Gemini API 호출 검증 테스트.

시뮬레이션 금지. 실제 API 응답만 유효.
Browser OAuth 인증 토큰을 사용하여 Codex/Gemini 엔드포인트 직접 호출.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("real_api_test")

# 결과 저장 경로
DEBATE_DIR = Path("C:/claude/ultimate-debate/.claude/debates/debate_real_api_verification")
DEBATE_DIR.mkdir(parents=True, exist_ok=True)


async def test_gpt_real_call():
    """GPT Codex API 실제 호출 검증."""
    from ultimate_debate.clients.openai_client import OpenAIClient

    logger.info("=" * 60)
    logger.info("GPT REAL API CALL TEST")
    logger.info("=" * 60)

    client = OpenAIClient()

    # Step 1: 인증
    logger.info("[1/3] Authenticating...")
    try:
        auth_ok = await client.ensure_authenticated()
        logger.info(f"  Auth result: {auth_ok}")
        logger.info(f"  Selected model: {client.model_name}")
        logger.info(f"  Discovered models: {client.discovered_models}")
    except Exception as e:
        logger.error(f"  Auth FAILED: {type(e).__name__}: {e}")
        return {"status": "AUTH_FAILED", "error": str(e)}

    # Step 2: analyze() 호출
    logger.info("[2/3] Calling analyze()...")
    task = (
        "Analyze the trade-offs of removing a forced sub-agent delegation "
        "workflow (OMC) from a Claude Code orchestration system, where the "
        "new /auto v21.0 workflow already handles 80% of the functionality "
        "via Agent Teams pattern. What are the key risks and benefits?"
    )

    try:
        result = await client.analyze(task)
        logger.info(f"  Response keys: {list(result.keys())}")
        logger.info(f"  Conclusion: {result.get('conclusion', 'N/A')[:100]}...")
        logger.info(f"  Confidence: {result.get('confidence', 'N/A')}")
        logger.info(f"  Key points count: {len(result.get('key_points', []))}")
    except Exception as e:
        logger.error(f"  analyze() FAILED: {type(e).__name__}: {e}")
        return {"status": "API_CALL_FAILED", "error": str(e), "phase": "analyze"}

    # Step 3: 결과 저장
    logger.info("[3/3] Saving results...")
    output = {
        "model": "gpt",
        "model_version": client.model_name,
        "discovered_models": client.discovered_models,
        "timestamp": datetime.now().isoformat(),
        "task": task,
        "result": result,
        "status": "SUCCESS",
    }

    output_path = DEBATE_DIR / "gpt_real_result.json"
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"  Saved to: {output_path}")

    # MD 파일도 생성
    md_path = DEBATE_DIR / "round_00" / "gpt.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_content = f"""# GPT Real API Analysis Result

## Model Info
- **Model**: {client.model_name}
- **Discovered Models**: {', '.join(client.discovered_models) if client.discovered_models else 'None'}
- **Timestamp**: {datetime.now().isoformat()}
- **API**: Codex CLI ({client.CODEX_API_BASE})

## Task
{task}

## Analysis
{result.get('analysis', 'N/A')}

## Conclusion
{result.get('conclusion', 'N/A')}

## Confidence
{result.get('confidence', 'N/A')}

## Key Points
{chr(10).join(f'- {p}' for p in result.get('key_points', []))}

## Suggested Steps
{chr(10).join(f'- {s}' for s in result.get('suggested_steps', []))}
"""
    md_path.write_text(md_content, encoding="utf-8")
    logger.info(f"  MD saved to: {md_path}")

    return output


async def test_gemini_real_call():
    """Gemini Code Assist API 실제 호출 검증."""
    from ultimate_debate.clients.gemini_client import GeminiClient

    logger.info("=" * 60)
    logger.info("GEMINI REAL API CALL TEST")
    logger.info("=" * 60)

    client = GeminiClient()

    # Step 1: 인증
    logger.info("[1/3] Authenticating...")
    try:
        auth_ok = await client.ensure_authenticated()
        logger.info(f"  Auth result: {auth_ok}")
        logger.info(f"  Selected model: {client.model_name}")
        logger.info(f"  Discovered models: {client.discovered_models[:5] if client.discovered_models else []}")
        logger.info(f"  Project ID: {client._discovered_project_id}")
        logger.info(f"  Mode: Code Assist={client.use_code_assist}")
    except Exception as e:
        logger.error(f"  Auth FAILED: {type(e).__name__}: {e}")
        return {"status": "AUTH_FAILED", "error": str(e)}

    # Step 2: analyze() 호출
    logger.info("[2/3] Calling analyze()...")
    task = (
        "Analyze the trade-offs of removing a forced sub-agent delegation "
        "workflow (OMC) from a Claude Code orchestration system, where the "
        "new /auto v21.0 workflow already handles 80% of the functionality "
        "via Agent Teams pattern. What are the key risks and benefits?"
    )

    try:
        result = await client.analyze(task)
        logger.info(f"  Response keys: {list(result.keys())}")
        logger.info(f"  Conclusion: {result.get('conclusion', 'N/A')[:100]}...")
        logger.info(f"  Confidence: {result.get('confidence', 'N/A')}")
        logger.info(f"  Key points count: {len(result.get('key_points', []))}")
    except Exception as e:
        logger.error(f"  analyze() FAILED: {type(e).__name__}: {e}")
        return {"status": "API_CALL_FAILED", "error": str(e), "phase": "analyze"}

    # Step 3: 결과 저장
    logger.info("[3/3] Saving results...")
    output = {
        "model": "gemini",
        "model_version": client.model_name,
        "discovered_models": client.discovered_models[:10] if client.discovered_models else [],
        "project_id": client._discovered_project_id,
        "timestamp": datetime.now().isoformat(),
        "task": task,
        "result": result,
        "status": "SUCCESS",
    }

    output_path = DEBATE_DIR / "gemini_real_result.json"
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"  Saved to: {output_path}")

    # MD 파일도 생성
    md_path = DEBATE_DIR / "round_00" / "gemini.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_content = f"""# Gemini Real API Analysis Result

## Model Info
- **Model**: {client.model_name}
- **Project ID**: {client._discovered_project_id}
- **Timestamp**: {datetime.now().isoformat()}
- **API**: Code Assist ({client.CODE_ASSIST_BASE})

## Task
{task}

## Analysis
{result.get('analysis', 'N/A')}

## Conclusion
{result.get('conclusion', 'N/A')}

## Confidence
{result.get('confidence', 'N/A')}

## Key Points
{chr(10).join(f'- {p}' for p in result.get('key_points', []))}

## Suggested Steps
{chr(10).join(f'- {s}' for s in result.get('suggested_steps', []))}
"""
    md_path.write_text(md_content, encoding="utf-8")
    logger.info(f"  MD saved to: {md_path}")

    return output


async def main():
    """메인 실행 - GPT와 Gemini 병렬 호출."""
    logger.info("=" * 60)
    logger.info("REAL API VERIFICATION TEST")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("NO SIMULATION. REAL API CALLS ONLY.")
    logger.info("=" * 60)

    # 병렬 실행
    gpt_result, gemini_result = await asyncio.gather(
        test_gpt_real_call(),
        test_gemini_real_call(),
        return_exceptions=True,
    )

    # 결과 요약
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 60)

    summary = {
        "timestamp": datetime.now().isoformat(),
        "gpt": {},
        "gemini": {},
    }

    if isinstance(gpt_result, Exception):
        logger.error(f"GPT: EXCEPTION - {type(gpt_result).__name__}: {gpt_result}")
        summary["gpt"] = {"status": "EXCEPTION", "error": str(gpt_result)}
    else:
        status = gpt_result.get("status", "UNKNOWN")
        model = gpt_result.get("model_version", "unknown")
        logger.info(f"GPT: {status} (model: {model})")
        summary["gpt"] = {"status": status, "model": model}

    if isinstance(gemini_result, Exception):
        logger.error(f"Gemini: EXCEPTION - {type(gemini_result).__name__}: {gemini_result}")
        summary["gemini"] = {"status": "EXCEPTION", "error": str(gemini_result)}
    else:
        status = gemini_result.get("status", "UNKNOWN")
        model = gemini_result.get("model_version", "unknown")
        logger.info(f"Gemini: {status} (model: {model})")
        summary["gemini"] = {"status": status, "model": model}

    # 요약 저장
    summary_path = DEBATE_DIR / "verification_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"\nSummary saved to: {summary_path}")

    # 종합 판정
    all_success = (
        not isinstance(gpt_result, Exception)
        and not isinstance(gemini_result, Exception)
        and gpt_result.get("status") == "SUCCESS"
        and gemini_result.get("status") == "SUCCESS"
    )

    if all_success:
        logger.info("\n✓ ALL REAL API CALLS VERIFIED SUCCESSFULLY")
        return 0
    else:
        logger.warning("\n✗ SOME API CALLS FAILED - See details above")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
