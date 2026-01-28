"""Claude AI Client for Ultimate Debate

Claude Code 토큰 재사용 기반 AI 클라이언트.
Browser OAuth 인증 방식 준수 (API 키 사용 금지).
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from ultimate_debate.auth import AuthToken, RetryLimitExceededError, TokenStore
from ultimate_debate.clients.base import BaseAIClient

logger = logging.getLogger(__name__)


class ClaudeClient(BaseAIClient):
    """Claude AI 클라이언트

    Claude Code의 내부 토큰을 재사용하여 Anthropic API에 접근.
    API 키 방식은 사용하지 않음 (CLAUDE.md 규칙 준수).

    Example:
        client = ClaudeClient(model_name="claude-3-5-sonnet")
        await client.ensure_authenticated()
        result = await client.analyze("코드 리뷰 요청", context)
    """

    API_BASE = "https://api.anthropic.com/v1"
    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(
        self,
        model_name: str = "claude-3-5-sonnet",
        token_store: TokenStore | None = None,
    ):
        super().__init__(model_name)
        self.token_store = token_store or TokenStore()
        self._token: str | None = None
        self._auth_retry_count = 0  # 재인증 재시도 카운터
        self._max_auth_retries = 1  # 최대 재시도 횟수

    async def ensure_authenticated(self) -> bool:
        """인증 상태 확인 및 Claude Code 토큰 획득

        Returns:
            bool: 인증 성공 여부

        Raises:
            ValueError: 토큰을 찾을 수 없을 때 해결 방법 안내
        """
        # 1. 저장된 토큰 확인
        stored_token = await self.token_store.load("anthropic")
        if stored_token and not stored_token.is_expired():
            self._token = stored_token.access_token
            logger.info("[ClaudeClient] 저장된 토큰 사용")
            return True

        # 2. Claude Code 토큰 재사용 시도
        claude_code_token = self._get_claude_code_token()
        if claude_code_token:
            self._token = claude_code_token
            # 토큰 저장 (다음 세션용)
            new_token = AuthToken(
                provider="anthropic",
                access_token=claude_code_token,
                token_type="bearer",
            )
            await self.token_store.save(new_token)
            logger.info("[ClaudeClient] Claude Code 토큰 발견 및 저장")
            return True

        # 3. 토큰 없으면 실패 - 명확한 에러 메시지
        logger.error("[ClaudeClient] 인증 토큰을 찾을 수 없음")
        return False

    def _get_claude_code_token(self) -> str | None:
        """Claude Code 내부 토큰 획득

        Claude Code가 사용하는 토큰을 찾아서 재사용.
        여러 가능한 위치를 순차적으로 확인.
        실패 시 시도한 경로를 로그에 기록합니다.

        Returns:
            str: 토큰 또는 None
        """
        # 검색할 경로들 (우선순위 순)
        search_paths = [
            # Claude Code 전용 경로
            Path.home() / ".claude" / "credentials.json",
            Path.home() / ".claude" / "settings.json",
            # macOS/Linux 표준 경로
            Path.home() / ".config" / "claude" / "settings.json",
            # Windows 경로
            Path(os.environ.get("APPDATA", "")) / "Claude" / "settings.json",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Claude" / "settings.json",
        ]

        tried_paths = []

        for path in search_paths:
            tried_paths.append(str(path))
            logger.debug(f"[ClaudeClient] 토큰 경로 확인: {path}")

            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)

                    # 다양한 키 형식 시도
                    token = (
                        data.get("auth_token")
                        or data.get("access_token")
                        or data.get("token")
                        or data.get("anthropic", {}).get("token")
                    )

                    if token:
                        logger.info(f"[ClaudeClient] 토큰 발견: {path}")
                        return token
                except (OSError, json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"[ClaudeClient] 토큰 파싱 실패 ({path}): {e}")
                    continue

        logger.warning(
            f"[ClaudeClient] 토큰을 찾을 수 없음. 시도한 경로: {tried_paths}"
        )
        return None

    async def _call_api(
        self,
        messages: list[dict],
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        """Anthropic API 호출

        Args:
            messages: 메시지 배열
            system: 시스템 프롬프트
            temperature: 창의성 조절 (0.0~1.0)
            max_tokens: 최대 토큰 수

        Returns:
            dict: 파싱된 JSON 응답
        """
        if not self._token:
            await self.ensure_authenticated()

        headers = {
            "x-api-key": self._token,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system:
            payload["system"] = system

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/messages",
                headers=headers,
                json=payload,
                timeout=120.0,
            )

            if response.status_code == 401:
                # 토큰 만료, 재인증 시도
                if self._auth_retry_count >= self._max_auth_retries:
                    raise RetryLimitExceededError(
                        "Authentication failed after retry. "
                        "Please re-login or check Claude Code credentials",
                        max_retries=self._max_auth_retries,
                        attempts=self._auth_retry_count,
                        provider="claude"
                    )
                self._auth_retry_count += 1
                self._token = None
                if await self.ensure_authenticated():
                    result = await self._call_api(
                        messages, system, temperature, max_tokens
                    )
                    self._auth_retry_count = 0  # 성공 시 리셋
                    return result
                raise RetryLimitExceededError(
                    "Authentication failed",
                    max_retries=self._max_auth_retries,
                    attempts=self._auth_retry_count,
                    provider="claude"
                )

            response.raise_for_status()
            result = response.json()

            # 응답 텍스트 추출 및 JSON 파싱
            content = result.get("content", [])
            if content and content[0].get("type") == "text":
                text = content[0].get("text", "{}")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    # JSON이 아니면 텍스트로 반환
                    return {"raw_text": text}

            return result

    async def analyze(
        self, task: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """태스크 분석

        Args:
            task: 분석할 태스크 설명
            context: 이전 라운드 컨텍스트

        Returns:
            dict: analysis, conclusion, confidence 포함
        """
        system_prompt = """당신은 코드 리뷰 및 기술적 분석을 수행하는 전문가입니다.
주어진 태스크를 분석하고 JSON 형식으로 응답하세요.

응답 형식:
{
    "analysis": "상세 분석 내용",
    "conclusion": "핵심 결론 (한 문장)",
    "confidence": 0.0~1.0 (확신도),
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", ...],
    "suggested_steps": ["단계 1", "단계 2", ...]
}"""

        user_message = f"태스크: {task}"
        if context:
            ctx_str = json.dumps(context, ensure_ascii=False, indent=2)
            user_message += f"\n\n이전 라운드 컨텍스트:\n{ctx_str}"

        messages = [{"role": "user", "content": user_message}]

        return await self._call_api(messages, system=system_prompt)

    async def review(
        self, task: str, peer_analysis: dict[str, Any], own_analysis: dict[str, Any]
    ) -> dict[str, Any]:
        """피어 분석 리뷰

        Args:
            task: 원본 태스크
            peer_analysis: 피어의 분석 결과
            own_analysis: 본인 분석 결과

        Returns:
            dict: feedback, agreement_points, disagreement_points 포함
        """
        system_prompt = """다른 AI의 분석을 리뷰하고 피드백을 제공하세요.
동의하는 점과 동의하지 않는 점을 명확히 구분하세요.

응답 형식:
{
    "feedback": "전반적인 피드백",
    "agreement_points": ["동의하는 점 1", "동의하는 점 2", ...],
    "disagreement_points": ["불일치 점 1: 이유", "불일치 점 2: 이유", ...],
    "suggested_improvements": ["개선 제안 1", "개선 제안 2", ...]
}"""

        user_message = f"""태스크: {task}

피어 분석:
{json.dumps(peer_analysis, ensure_ascii=False, indent=2)}

본인 분석:
{json.dumps(own_analysis, ensure_ascii=False, indent=2)}"""

        messages = [{"role": "user", "content": user_message}]

        return await self._call_api(messages, system=system_prompt)

    async def debate(
        self,
        task: str,
        own_position: dict[str, Any],
        opposing_views: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """토론 라운드 참여

        Args:
            task: 원본 태스크
            own_position: 현재 입장
            opposing_views: 상대측 견해들

        Returns:
            dict: updated_position, rebuttals, concessions 포함
        """
        system_prompt = """토론에 참여하여 입장을 발전시키세요.
상대 의견에 대한 반박과 수용할 점을 구분하세요.

응답 형식:
{
    "updated_position": {
        "conclusion": "업데이트된 결론",
        "confidence": 0.0~1.0,
        "key_points": ["핵심 포인트들"]
    },
    "rebuttals": ["반박 1", "반박 2", ...],
    "concessions": ["수용 1: 이유", "수용 2: 이유", ...],
    "remaining_disagreements": ["남은 불일치 1", ...]
}"""

        opposing_views_str = "\n\n".join(
            [
                f"모델 {i+1}:\n{json.dumps(view, ensure_ascii=False, indent=2)}"
                for i, view in enumerate(opposing_views)
            ]
        )

        user_message = f"""태스크: {task}

본인 입장:
{json.dumps(own_position, ensure_ascii=False, indent=2)}

상대 견해들:
{opposing_views_str}"""

        messages = [{"role": "user", "content": user_message}]

        return await self._call_api(messages, system=system_prompt)
