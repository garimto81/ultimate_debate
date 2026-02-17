"""Ultimate debate engine with 5-phase workflow.

Claude Code가 오케스트레이터로서 직접 분석에 참여하고,
외부 AI(GPT, Gemini)와 협업하는 Multi-AI Consensus Engine.

Note:
    ClaudeClient는 더 이상 사용하지 않음.
    Claude Code 자체가 Claude이므로, API 호출 대신 직접 분석 수행.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from ultimate_debate.clients.base import BaseAIClient
from ultimate_debate.consensus.protocol import ConsensusChecker, ConsensusResult
from ultimate_debate.storage.context_manager import DebateContextManager

logger = logging.getLogger(__name__)


class NoAvailableClientsError(Exception):
    """Raised when no AI clients are available for analysis.

    이 에러는 다음 상황에서 발생합니다:
    - ai_clients가 비어 있고
    - include_claude_self=False이거나 Claude 분석이 설정되지 않음

    해결 방법:
    1. register_ai_client()로 외부 AI(GPT, Gemini)를 등록하거나
    2. include_claude_self=True로 설정하고 set_claude_analysis() 호출
    """


class UltimateDebate:
    """Orchestrate multi-AI debate with consensus checking.

    Claude Code가 오케스트레이터이자 참여자로서 동작:
    - 외부 AI (GPT, Gemini): register_ai_client()로 등록
    - Claude: include_claude_self=True면 자체 분석 참여 (API 호출 없음)

    Example:
        # 올바른 사용 예시 (3AI 토론)
        debate = UltimateDebate(
            task="API 설계 리뷰",
            include_claude_self=True  # Claude Code 자체 참여
        )

        # 외부 AI만 등록 (Claude는 자동 참여)
        debate.register_ai_client("gpt", OpenAIClient("gpt-5.2-codex"))
        debate.register_ai_client("gemini", GeminiClient("gemini-2.5-flash"))

        result = await debate.run()
    """

    def __init__(
        self,
        task: str,
        task_id: str | None = None,
        max_rounds: int = 5,
        consensus_threshold: float = 0.8,
        include_claude_self: bool = True,
        strict: bool = False,
    ):
        """Initialize debate orchestrator.

        Args:
            task: Task description to debate
            task_id: Optional task ID (generated if not provided)
            max_rounds: Maximum debate rounds before forced conclusion
            consensus_threshold: Minimum agreement ratio for full consensus
            include_claude_self: Claude Code 자체가 분석에 참여할지 여부.
                True(기본값)면 Claude Code가 직접 분석 결과를 제공.
                API 호출 없이 오케스트레이터 자체가 Claude 역할 수행.
            strict: Strict 모드. True면 외부 AI가 최소 1개 필수.
                False(기본값)면 include_claude_self=True 시 Claude만으로도 동작.
        """
        self.task = task
        self.task_id = task_id or self._generate_task_id()
        self.round = 0
        self.max_rounds = max_rounds
        self.consensus_threshold = consensus_threshold
        self.include_claude_self = include_claude_self
        self.strict = strict

        # Initialize components
        self.context_manager = DebateContextManager(self.task_id)
        self.consensus_checker = ConsensusChecker(threshold=consensus_threshold)

        # AI clients (외부 AI만: GPT, Gemini 등)
        # Claude는 등록하지 않음 - include_claude_self로 자체 참여
        self.ai_clients: dict[str, BaseAIClient] = {}

        # Debate state
        self.current_analyses: dict[str, dict[str, Any]] = {}
        self.consensus_result: ConsensusResult | None = None
        self.failed_clients: dict[str, str] = {}

        # Claude 자체 분석 결과 저장 (외부에서 주입)
        self._claude_self_analysis: dict[str, Any] | None = None

    def _generate_task_id(self) -> str:
        """Generate unique task ID.

        Returns:
            UUID-based task ID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"debate_{timestamp}_{short_uuid}"

    def register_ai_client(self, model_name: str, client: BaseAIClient) -> None:
        """Register an external AI client for debate.

        Note:
            Claude는 등록하지 마세요! Claude Code가 이미 Claude입니다.
            include_claude_self=True로 자동 참여합니다.

        Args:
            model_name: Model identifier (gpt/gemini 등 외부 AI)
            client: AI client instance

        Raises:
            ValueError: 'claude'를 등록하려 할 때
        """
        if model_name.lower() == "claude":
            raise ValueError(
                "Claude 클라이언트를 등록하지 마세요! "
                "Claude Code가 이미 Claude입니다. "
                "include_claude_self=True(기본값)로 자동 참여합니다."
            )
        self.ai_clients[model_name] = client

    def set_claude_analysis(self, analysis: dict[str, Any]) -> None:
        """Claude Code의 자체 분석 결과 설정.

        Claude Code(오케스트레이터)가 직접 분석한 결과를 주입합니다.
        API 호출 없이 Claude의 관점을 토론에 반영.

        Args:
            analysis: Claude의 분석 결과
                - analysis: 상세 분석 내용
                - conclusion: 핵심 결론
                - confidence: 확신도 (0.0~1.0)
                - key_points: 핵심 포인트 리스트
        """
        self._claude_self_analysis = {
            "model": "claude",
            "model_version": "claude-code-self",  # Claude Code 자체
            **analysis,
        }

    async def run(self) -> dict[str, Any]:
        """Run complete debate workflow.

        Returns:
            Final debate result with consensus and strategy
        """
        # Save initial task
        self.context_manager.save_task(
            self.task,
            {
                "created_at": datetime.now().isoformat(),
                "max_rounds": self.max_rounds,
                "status": "RUNNING",
            },
        )

        # Strict mode: 외부 AI 필수 검증
        if self.strict and not self.ai_clients:
            raise NoAvailableClientsError(
                "Strict 모드: 외부 AI(GPT, Gemini) 최소 1개 등록 필수.\n"
                "register_ai_client()로 외부 AI를 등록하세요."
            )

        # Preflight: 등록된 외부 AI 클라이언트 건강 확인
        if self.ai_clients:
            logger.info("Preflight: checking client authentication...")
            dead_clients = []

            for model_name, client in list(self.ai_clients.items()):
                try:
                    await asyncio.wait_for(
                        client.ensure_authenticated(),
                        timeout=30.0
                    )
                    logger.info(f"✓ {model_name} preflight passed")
                except TimeoutError:
                    error_msg = "Preflight timeout (30s)"
                    logger.warning(f"✗ {model_name} {error_msg}")
                    self.failed_clients[model_name] = error_msg
                    dead_clients.append(model_name)
                except Exception as e:
                    error_msg = f"Preflight failed: {e}"
                    logger.warning(f"✗ {model_name} {error_msg}")
                    self.failed_clients[model_name] = error_msg
                    dead_clients.append(model_name)

            # 실패 클라이언트 제거
            for model_name in dead_clients:
                del self.ai_clients[model_name]

            # Strict 모드에서 모든 클라이언트 실패 시 에러
            if self.strict and not self.ai_clients:
                raise NoAvailableClientsError(
                    f"Preflight 실패: 모든 외부 AI 사용 불가.\n"
                    f"실패 클라이언트: {list(self.failed_clients.keys())}\n"
                    f"상세: {self.failed_clients}"
                )

        while self.round < self.max_rounds:
            print(f"\n=== Round {self.round} ===")

            # Phase 1: Parallel analysis
            print("Phase 1: Parallel Analysis")
            analyses = await self.run_parallel_analysis()

            # Phase 2: Consensus check (initial)
            print("Phase 2: Initial Consensus Check")
            self.consensus_result = self.consensus_checker.check_consensus(
                list(analyses.values())
            )

            # Save consensus result
            self.context_manager.save_consensus_result(
                self.round,
                {
                    "status": self.consensus_result.status,
                    "agreed_items": self.consensus_result.agreed_items,
                    "disputed_items": self.consensus_result.disputed_items,
                    "consensus_percentage": self.consensus_result.consensus_percentage,
                    "next_action": self.consensus_result.next_action,
                },
            )

            # Check if consensus reached
            if self.is_consensus_reached():
                pct = self.consensus_result.consensus_percentage * 100
                print(f"Consensus reached! ({pct:.1f}%)")
                break

            # Phase 3: Cross review
            if self.consensus_result.next_action == "CROSS_REVIEW":
                print("Phase 3: Cross Review")
                reviews = await self.run_cross_review()

                # 플레이스홀더 리뷰 필터링
                real_reviews = {
                    k: v for k, v in reviews.items()
                    if not v.get("requires_input")
                }

                # Re-check consensus after review
                review_consensus = self.consensus_checker.check_cross_review_consensus(
                    list(real_reviews.values())
                )

                if review_consensus.status == "FULL_CONSENSUS":
                    self.consensus_result = review_consensus
                    break

            # Phase 4: Debate round
            if self.consensus_result.next_action == "DEBATE":
                print("Phase 4: Debate Round")
                debate_results = await self.run_debate_round()

                # Update analyses with debate results
                for model, result in debate_results.items():
                    updated = result.get("updated_position", "")
                    if isinstance(updated, dict):
                        conclusion = updated.get("conclusion", "")
                        self.current_analyses[model]["conclusion"] = conclusion
                    else:
                        self.current_analyses[model]["conclusion"] = updated

            self.round += 1

        # Phase 5: Final strategy
        print("Phase 5: Final Strategy")
        final_result = self.get_final_strategy()

        # Generate FINAL.md
        self.context_manager.generate_final_md(final_result)

        return final_result

    async def run_parallel_analysis(self) -> dict[str, dict[str, Any]]:
        """Phase 1: Run parallel analysis from all AI models.

        외부 AI(GPT, Gemini)는 API 호출, Claude는 자체 분석 결과 사용.

        Returns:
            Dict mapping model name to analysis result
        """
        analyses = {}

        # 1. 외부 AI 병렬 호출 (GPT, Gemini 등)
        if self.ai_clients:
            tasks = []
            model_names = []

            for model_name, client in self.ai_clients.items():
                tasks.append(client.analyze(self.task))
                model_names.append(model_name)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for model_name, result in zip(model_names, results, strict=True):
                # 개별 클라이언트 실패 시 graceful skip
                if isinstance(result, Exception):
                    logger.warning(f"{model_name} analysis failed: {result}")
                    self.failed_clients[model_name] = str(result)
                    continue

                # 결과 무결성 검증
                if not self._validate_analysis(model_name, result):
                    error_msg = "분석 결과 무결성 검증 실패"
                    logger.warning(f"{model_name}: {error_msg}")
                    self.failed_clients[model_name] = error_msg
                    continue

                # API 응답의 정확한 모델 버전 보존 (존재 시)
                if "model_version" not in result:
                    result["model_version"] = result.get("model", model_name)
                result["model"] = model_name  # 등록 키 (파일명용)
                analyses[model_name] = result

                # Save to context
                self.context_manager.save_round(self.round, model_name, result)

        # 2. Claude Code 자체 분석 추가 (API 호출 없음)
        if self.include_claude_self:
            claude_analysis = self._get_claude_self_analysis()

            # Claude 분석도 검증 (플레이스홀더 필터링)
            if self._validate_analysis("claude", claude_analysis):
                analyses["claude"] = claude_analysis
                self.context_manager.save_round(
                    self.round, "claude", claude_analysis
                )
            else:
                logger.warning(
                    "Claude 자체 분석이 유효하지 않음 "
                    "(set_claude_analysis() 호출 필요)"
                )
                self.failed_clients["claude"] = (
                    "플레이스홀더 분석 (set_claude_analysis() 미호출)"
                )

        # 3. 클라이언트도 없고 Claude 자체 참여도 없으면 에러
        if not analyses:
            raise NoAvailableClientsError(
                "분석 가능한 AI 클라이언트가 없습니다.\n"
                "해결 방법:\n"
                "1. register_ai_client()로 외부 AI(GPT, Gemini)를 등록하거나\n"
                "2. include_claude_self=True를 설정하고 "
                "set_claude_analysis()를 호출하세요."
            )

        self.current_analyses = analyses
        return analyses

    def _get_claude_self_analysis(self) -> dict[str, Any]:
        """Claude Code의 자체 분석 결과 반환.

        set_claude_analysis()로 설정된 결과가 있으면 사용,
        없으면 플레이스홀더 반환 (실제 사용 시 반드시 설정 필요).

        Returns:
            Claude의 분석 결과 dict
        """
        if self._claude_self_analysis:
            return self._claude_self_analysis

        # 플레이스홀더 - 실제 사용 시 set_claude_analysis()로 설정해야 함
        return {
            "model": "claude",
            "model_version": "claude-code-self",
            "analysis": "[Claude Code 분석 대기 중 - set_claude_analysis() 호출 필요]",
            "conclusion": "[분석 결과를 set_claude_analysis()로 설정하세요]",
            "confidence": 0.0,
            "key_points": [],
            "requires_input": True,  # 입력 필요 플래그
        }

    def _validate_analysis(self, model: str, result: dict[str, Any]) -> bool:
        """Validate that analysis result is a genuine API response.

        검증 항목:
        1. 필수 필드 존재 (analysis, conclusion, confidence)
        2. 최소 분석 길이 (50자 이상)
        3. confidence 값 범위 (0.0~1.0)

        Args:
            model: Model name for logging
            result: Analysis result to validate

        Returns:
            True if valid, False if invalid

        Note:
            플레이스홀더 분석 (requires_input=True)도 유효하지 않은 것으로 처리.
        """
        # 플레이스홀더 체크
        if result.get("requires_input"):
            logger.warning(f"{model}: 플레이스홀더 분석 (requires_input=True)")
            return False

        # 필수 필드 검증
        required_fields = ["analysis", "conclusion", "confidence"]
        missing = [f for f in required_fields if f not in result]
        if missing:
            logger.warning(f"{model}: 필수 필드 누락 {missing}")
            return False

        # 최소 분석 길이 검증 (실제 분석은 최소 50자 이상)
        analysis_text = result.get("analysis", "")
        if not isinstance(analysis_text, str) or len(analysis_text) < 50:
            logger.warning(
                f"{model}: 분석이 너무 짧음 ({len(analysis_text)}자). "
                f"최소 50자 이상 필요."
            )
            return False

        # confidence 범위 검증
        confidence = result.get("confidence", 0)
        if not isinstance(confidence, int | float):
            logger.warning(
                f"{model}: confidence가 숫자가 아님 ({type(confidence)})"
            )
            return False
        if not (0 <= confidence <= 1):
            logger.warning(f"{model}: confidence 범위 초과 ({confidence})")
            return False

        return True

    async def run_cross_review(self) -> dict[str, dict[str, Any]]:
        """Phase 2: Run cross-review between models.

        외부 AI끼리의 리뷰는 API 호출, Claude 관련 리뷰는 별도 처리.

        Returns:
            Dict mapping reviewer-reviewed pair to review result
        """
        if not self.ai_clients and not self.include_claude_self:
            # Placeholder: mock reviews
            return self._mock_cross_review()

        reviews = {}
        tasks = []
        review_keys = []

        # 1. 외부 AI가 다른 모델을 리뷰 (Claude 포함)
        for reviewer_name, reviewer_client in self.ai_clients.items():
            # 분석 실패한 클라이언트는 리뷰에서 제외
            if reviewer_name not in self.current_analyses:
                logger.warning(f"{reviewer_name} skipped in cross review (no analysis)")
                continue

            for reviewed_name, reviewed_analysis in self.current_analyses.items():
                if reviewer_name == reviewed_name:
                    continue

                own_analysis = self.current_analyses[reviewer_name]

                tasks.append(
                    reviewer_client.review(self.task, reviewed_analysis, own_analysis)
                )
                review_keys.append((reviewer_name, reviewed_name))

        if tasks:
            results = await asyncio.gather(*tasks)

            for (reviewer_name, reviewed_name), result in zip(
                review_keys, results, strict=True
            ):
                key = f"{reviewer_name}_reviews_{reviewed_name}"
                reviews[key] = result

                # Save to context
                self.context_manager.save_cross_review(
                    self.round, reviewer_name, reviewed_name, result
                )

        # 2. Claude가 다른 모델을 리뷰 (외부 주입 또는 플레이스홀더)
        if self.include_claude_self and "claude" in self.current_analyses:
            for reviewed_name, reviewed_analysis in self.current_analyses.items():
                if reviewed_name == "claude":
                    continue

                key = f"claude_reviews_{reviewed_name}"
                # Claude의 리뷰는 외부에서 set_claude_review()로 설정하거나 플레이스홀더
                review = self._get_claude_review_for(reviewed_name, reviewed_analysis)
                reviews[key] = review

                self.context_manager.save_cross_review(
                    self.round, "claude", reviewed_name, review
                )

        return reviews

    def set_claude_review(self, reviewed_model: str, review: dict[str, Any]) -> None:
        """Claude Code의 리뷰 결과 설정.

        Args:
            reviewed_model: 리뷰 대상 모델 (gpt, gemini 등)
            review: 리뷰 결과
                - feedback: 전반적인 피드백
                - agreement_points: 동의하는 점 리스트
                - disagreement_points: 불일치 점 리스트
        """
        if not hasattr(self, "_claude_reviews"):
            self._claude_reviews: dict[str, dict[str, Any]] = {}
        self._claude_reviews[reviewed_model] = review

    def _get_claude_review_for(
        self, reviewed_model: str, reviewed_analysis: dict[str, Any]
    ) -> dict[str, Any]:
        """Claude의 특정 모델 리뷰 결과 반환."""
        if hasattr(self, "_claude_reviews") and reviewed_model in self._claude_reviews:
            return self._claude_reviews[reviewed_model]

        # 플레이스홀더
        return {
            "feedback": f"[Claude의 {reviewed_model} 리뷰 대기 중]",
            "agreement_points": [],
            "disagreement_points": [],
            "requires_input": True,
        }

    def is_consensus_reached(self) -> bool:
        """Phase 3: Check if consensus is reached.

        Returns:
            True if full consensus reached
        """
        if not self.consensus_result:
            return False

        return self.consensus_result.status == "FULL_CONSENSUS"

    async def run_debate_round(self) -> dict[str, dict[str, Any]]:
        """Phase 4: Run debate round for disputed items.

        Returns:
            Dict mapping model name to updated position
        """
        if not self.ai_clients and not self.include_claude_self:
            # Placeholder: mock debate
            return self._mock_debate_round()

        debates = {}
        tasks = []
        model_names = []

        # 1. 외부 AI 토론 참여
        for model_name, client in self.ai_clients.items():
            # 분석 실패한 클라이언트는 토론에서 제외
            if model_name not in self.current_analyses:
                logger.warning(f"{model_name} skipped in debate (no analysis)")
                continue

            own_position = self.current_analyses[model_name]
            opposing_views = [
                analysis
                for name, analysis in self.current_analyses.items()
                if name != model_name
            ]

            tasks.append(client.debate(self.task, own_position, opposing_views))
            model_names.append(model_name)

        if tasks:
            results = await asyncio.gather(*tasks)

            for model_name, result in zip(model_names, results, strict=True):
                debates[model_name] = result

                # Save to context
                self.context_manager.save_debate_round(self.round, model_name, result)

        # 2. Claude 토론 참여 (외부 주입 또는 플레이스홀더)
        if self.include_claude_self and "claude" in self.current_analyses:
            debate_result = self._get_claude_debate_result()
            debates["claude"] = debate_result
            self.context_manager.save_debate_round(self.round, "claude", debate_result)

        return debates

    def set_claude_debate(self, debate_result: dict[str, Any]) -> None:
        """Claude Code의 토론 결과 설정.

        Args:
            debate_result: 토론 결과
                - updated_position: 업데이트된 입장
                - rebuttals: 반박 리스트
                - concessions: 수용 리스트
        """
        self._claude_debate_result = debate_result

    def _get_claude_debate_result(self) -> dict[str, Any]:
        """Claude의 토론 결과 반환."""
        if hasattr(self, "_claude_debate_result") and self._claude_debate_result:
            return self._claude_debate_result

        # 플레이스홀더
        return {
            "updated_position": "[Claude의 토론 결과 대기 중]",
            "rebuttals": [],
            "concessions": [],
            "requires_input": True,
        }

    async def run_verification(self) -> dict[str, Any]:
        """Phase 4.2 전용 축약 워크플로우.

        전체 5-phase 대신 analyze → consensus check만 수행.
        검증 목적이므로 debate round 없이 1회 분석 후 합의 판정.

        Returns:
            Verification result with consensus status and analyses
        """
        analyses = await self.run_parallel_analysis()
        self.consensus_result = self.consensus_checker.check_consensus(
            list(analyses.values())
        )
        return {
            "status": self.consensus_result.status,
            "consensus_percentage": self.consensus_result.consensus_percentage,
            "agreed_items": self.consensus_result.agreed_items,
            "disputed_items": self.consensus_result.disputed_items,
            "analyses": {k: v.get("conclusion", "") for k, v in analyses.items()},
        }

    def get_final_strategy(self) -> dict[str, Any]:
        """Phase 5: Generate final strategy from consensus.

        Returns:
            Final result dict with strategy and metadata
        """
        if not self.consensus_result:
            return {
                "status": "FAILED",
                "final_strategy": {},
                "total_rounds": self.round,
                "consensus_percentage": 0.0,
                "task_id": self.task_id,
            }

        # Extract final strategy from agreed items
        final_strategy = {}
        if self.consensus_result.agreed_items:
            most_agreed = self.consensus_result.agreed_items[0]
            final_strategy = {
                "conclusion": most_agreed.get("conclusion", ""),
                "supporting_models": most_agreed.get("models", []),
                "confidence": self.consensus_result.consensus_percentage,
            }

        return {
            "status": self.consensus_result.status,
            "final_strategy": final_strategy,
            "total_rounds": self.round,
            "consensus_percentage": self.consensus_result.consensus_percentage,
            "task_id": self.task_id,
            "agreed_items": self.consensus_result.agreed_items,
            "disputed_items": self.consensus_result.disputed_items,
        }

    def get_status(self) -> dict[str, Any]:
        """Get current debate status.

        Returns:
            Status dict
        """
        context_status = self.context_manager.get_status()

        # 참여 모델 목록 (외부 AI + Claude 자체)
        participating_models = list(self.ai_clients.keys())
        if self.include_claude_self:
            participating_models.append("claude (self)")

        return {
            "task_id": self.task_id,
            "current_round": self.round,
            "max_rounds": self.max_rounds,
            "consensus_status": (
                self.consensus_result.status if self.consensus_result else "PENDING"
            ),
            "consensus_percentage": (
                self.consensus_result.consensus_percentage
                if self.consensus_result
                else 0.0
            ),
            "registered_models": list(self.ai_clients.keys()),  # 외부 AI만
            "participating_models": participating_models,  # Claude 포함 전체
            "include_claude_self": self.include_claude_self,
            "failed_clients": self.failed_clients,
            "context": context_status,
        }

    # Placeholder methods for testing without real AI clients
    def _mock_parallel_analysis(self) -> dict[str, dict[str, Any]]:
        """Generate mock parallel analysis results."""
        models = ["claude", "gpt", "gemini"]
        analyses = {}

        for model in models:
            analysis = {
                "model": model,
                "analysis": f"Mock analysis from {model}",
                "conclusion": f"Mock conclusion from {model}",
                "confidence": 0.85,
            }
            analyses[model] = analysis
            self.context_manager.save_round(self.round, model, analysis)

        self.current_analyses = analyses
        return analyses

    def _mock_cross_review(self) -> dict[str, dict[str, Any]]:
        """Generate mock cross-review results."""
        models = ["claude", "gpt", "gemini"]
        reviews = {}

        for reviewer in models:
            for reviewed in models:
                if reviewer == reviewed:
                    continue

                review = {
                    "feedback": f"{reviewer} reviews {reviewed}",
                    "agreement_points": ["Point 1", "Point 2"],
                    "disagreement_points": ["Point 3"],
                }
                key = f"{reviewer}_reviews_{reviewed}"
                reviews[key] = review

                self.context_manager.save_cross_review(
                    self.round, reviewer, reviewed, review
                )

        return reviews

    def _mock_debate_round(self) -> dict[str, dict[str, Any]]:
        """Generate mock debate round results."""
        models = ["claude", "gpt", "gemini"]
        debates = {}

        for model in models:
            debate = {
                "updated_position": f"Updated position from {model}",
                "rebuttals": ["Rebuttal 1", "Rebuttal 2"],
                "concessions": ["Concession 1"],
            }
            debates[model] = debate

            self.context_manager.save_debate_round(self.round, model, debate)

        return debates
