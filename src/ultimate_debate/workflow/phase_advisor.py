"""Phase-specific advisor using multi-LLM analysis."""

import logging
from typing import Any

from ultimate_debate.engine import UltimateDebate
from ultimate_debate.workflow.client_pool import ClientPool

logger = logging.getLogger(__name__)


class PhaseAdvisor:
    """Provides LLM-backed advisory for each PDCA phase.

    Each method corresponds to a specific phase checkpoint:
    - Phase 1.0: Codebase analysis (Gemini)
    - Phase 1.2: Plan review (GPT)
    - Phase 4.2: Implementation verification (3AI)
    - Phase 5: Results summarization (Gemini)
    """

    def __init__(self, client_pool: ClientPool) -> None:
        """Initialize advisor with client pool.

        Args:
            client_pool: Initialized ClientPool instance
        """
        self.pool = client_pool

    async def analyze_codebase(
        self, task: str, file_list: list[str]
    ) -> dict[str, Any]:
        """Phase 1.0: Large-scale codebase analysis via Gemini.

        Args:
            task: Task description
            file_list: List of file paths to analyze

        Returns:
            Analysis result or skip marker if Gemini unavailable
        """
        gemini = await self.pool.get_client("gemini")
        if not gemini:
            logger.warning("Gemini unavailable, skipping codebase analysis")
            return {"skipped": True, "reason": "Gemini unavailable"}

        try:
            return await gemini.analyze(task, context={"files": file_list})
        except Exception as e:
            logger.error(f"Gemini codebase analysis failed: {e}")
            return {"skipped": True, "reason": f"Gemini API error: {e}"}

    async def review_plan(self, task: str, plan_content: str) -> dict[str, Any]:
        """Phase 1.2: Plan review via GPT.

        Args:
            task: Task description
            plan_content: Plan markdown content to review

        Returns:
            Review result or skip marker if GPT unavailable
        """
        gpt = await self.pool.get_client("gpt")
        if not gpt:
            logger.warning("GPT unavailable, skipping plan review")
            return {"skipped": True, "reason": "GPT unavailable"}

        try:
            return await gpt.review(task, {"analysis": plan_content}, {})
        except Exception as e:
            logger.error(f"GPT plan review failed: {e}")
            return {"skipped": True, "reason": f"GPT API error: {e}"}

    async def verify_implementation(
        self, task: str, code_summary: str, claude_verdict: dict[str, Any]
    ) -> dict[str, Any]:
        """Phase 4.2: Multi-perspective verification via 3AI.

        Uses UltimateDebate engine with available LLMs + Claude's self-analysis.

        Args:
            task: Task description
            code_summary: Implementation summary
            claude_verdict: Claude's own verification result

        Returns:
            Verification result with consensus status and analyses.
            On error, returns {"status": "ERROR", "error": str, "analyses": {}}.
        """
        try:
            debate = UltimateDebate(
                task=f"코드 검증: {task}",
                include_claude_self=True,
                max_rounds=2,
                consensus_threshold=0.8,
            )

            gpt = await self.pool.get_client("gpt")
            if gpt:
                debate.register_ai_client("gpt", gpt)
                logger.info("✓ GPT registered for verification")

            gemini = await self.pool.get_client("gemini")
            if gemini:
                debate.register_ai_client("gemini", gemini)
                logger.info("✓ Gemini registered for verification")

            debate.set_claude_analysis(claude_verdict)

            return await debate.run_verification()

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return {"status": "ERROR", "error": str(e), "analyses": {}}

    async def summarize_results(
        self, task: str, results: dict[str, Any]
    ) -> dict[str, Any]:
        """Phase 5: Results summarization via Gemini.

        Args:
            task: Task description
            results: PDCA cycle results

        Returns:
            Summary or skip marker if Gemini unavailable
        """
        gemini = await self.pool.get_client("gemini")
        if not gemini:
            logger.warning("Gemini unavailable, skipping results summary")
            return {"skipped": True, "reason": "Gemini unavailable"}

        try:
            return await gemini.analyze(f"PDCA 결과 요약: {task}", context=results)
        except Exception as e:
            logger.error(f"Gemini results summary failed: {e}")
            return {"skipped": True, "reason": f"Gemini API error: {e}"}
