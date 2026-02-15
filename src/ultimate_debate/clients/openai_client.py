"""OpenAI Client for Ultimate Debate

ChatGPT Plus/Pro 구독자용 AI 클라이언트.
Browser OAuth 인증과 연동.

Codex CLI 호환 - chatgpt.com/backend-api/codex/responses 엔드포인트 사용.
"""

import json
import logging
import uuid
from typing import Any

import httpx

from ultimate_debate.auth import AuthToken, RetryLimitExceededError, TokenStore
from ultimate_debate.auth.providers import OpenAIProvider
from ultimate_debate.clients.base import BaseAIClient

logger = logging.getLogger(__name__)


class OpenAIClient(BaseAIClient):
    """OpenAI GPT 클라이언트

    ChatGPT Plus/Pro 구독자 전용.
    Browser OAuth로 인증하여 GPT-4/GPT-5 모델 접근.

    Codex CLI 호환 엔드포인트 사용:
    - chatgpt.com/backend-api/codex/responses (구독 기반)
    - api.openai.com/v1 (API 키 기반, fallback)

    Example:
        client = OpenAIClient(model_name="gpt-5-codex")
        await client.ensure_authenticated()
        result = await client.analyze("코드 리뷰 요청", context)
    """

    # Codex CLI 호환 엔드포인트 (ChatGPT Plus/Pro 구독 기반)
    CODEX_API_BASE = "https://chatgpt.com/backend-api/codex"
    # 기존 OpenAI API (API 키 기반, fallback)
    API_BASE = "https://api.openai.com/v1"

    # 기본 시스템 지시사항 (Codex API 필수)
    DEFAULT_INSTRUCTIONS = (
        "You are a helpful AI assistant specialized in "
        "code analysis, review, and technical discussions. "
        "Respond in JSON format when requested. "
        "Be precise and thorough in your analysis."
    )

    def __init__(
        self, model_name: str = "gpt-4o", token_store: TokenStore | None = None
    ):
        super().__init__(model_name)
        self.token_store = token_store or TokenStore()
        self.provider = OpenAIProvider()
        self._token: AuthToken | None = None
        self._auth_retry_count = 0  # 재인증 재시도 카운터
        self._max_auth_retries = 1  # 최대 재시도 횟수

    async def ensure_authenticated(self) -> bool:
        """인증 상태 확인 및 필요시 로그인

        Returns:
            bool: 인증 성공 여부
        """
        # 저장된 토큰 확인
        self._token = await self.token_store.load("openai")

        if self._token:
            # 토큰 유효성 확인
            if not self._token.is_expired():
                return True

            # 만료된 경우 갱신 시도
            if self._token.refresh_token:
                try:
                    self._token = await self.provider.refresh(self._token)
                    await self.token_store.save(self._token)
                    return True
                except ValueError:
                    pass  # 갱신 실패, 재로그인 필요

        # 새 로그인
        self._token = await self.provider.login()
        await self.token_store.save(self._token)
        return True

    async def _call_api(
        self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096
    ) -> dict:
        """OpenAI API 호출 (Codex API 우선)

        Args:
            messages: 메시지 배열
            temperature: 창의성 조절 (0.0~2.0)
            max_tokens: 최대 토큰 수

        Returns:
            dict: API 응답 (Chat Completions 형식으로 정규화)
        """
        if not self._token:
            await self.ensure_authenticated()

        # Codex API 형식으로 요청 (ChatGPT Plus/Pro 구독 기반)
        return await self._call_codex_api(messages, temperature, max_tokens)

    async def _call_codex_api(
        self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096
    ) -> dict:
        """Codex CLI 호환 API 호출 (스트리밍 필수)

        chatgpt.com/backend-api/codex/responses 엔드포인트 사용.
        OpenAI Codex API는 stream=true가 필수입니다.

        Args:
            messages: 메시지 배열 (role: system/user/assistant)
            temperature: 창의성 조절
            max_tokens: 최대 토큰 수

        Returns:
            dict: Chat Completions 형식으로 정규화된 응답
        """
        # 메시지를 Codex input 형식으로 변환
        # system → developer, user → user, assistant → assistant
        codex_input = []
        system_content = self.DEFAULT_INSTRUCTIONS

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_content = content
            elif role == "user":
                codex_input.append({"role": "user", "content": content})
            elif role == "assistant":
                codex_input.append({"role": "assistant", "content": content})

        # developer 역할로 시스템 프롬프트 추가 (맨 앞에)
        if system_content:
            codex_input.insert(0, {"role": "developer", "content": system_content})

        payload = {
            "model": self.model_name,
            "instructions": self.DEFAULT_INSTRUCTIONS,
            "input": codex_input,
            "tools": [],
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "reasoning": {"summary": "auto"},
            "store": False,
            "stream": True,  # Codex API는 스트리밍 필수!
            "include": ["reasoning.encrypted_content"],
            "prompt_cache_key": str(uuid.uuid4()),
        }

        async with httpx.AsyncClient() as client, client.stream(
            "POST",
            f"{self.CODEX_API_BASE}/responses",
            headers={
                "Authorization": f"Bearer {self._token.access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120.0,
        ) as response:
            if response.status_code == 401:
                # 토큰 만료, 재인증 시도
                if self._auth_retry_count >= self._max_auth_retries:
                    raise RetryLimitExceededError(
                        "Authentication failed after retry. "
                        "Please re-login with /ai-login openai",
                        max_retries=self._max_auth_retries,
                        attempts=self._auth_retry_count,
                        provider="openai"
                    )
                self._auth_retry_count += 1
                await self.ensure_authenticated()
                result = await self._call_codex_api(
                    messages, temperature, max_tokens
                )
                self._auth_retry_count = 0  # 성공 시 리셋
                return result

            if response.status_code != 200:
                # Codex API 실패 시 에러 내용 포함
                body = await response.aread()
                error_detail = body.decode()[:500] if body else "Unknown error"
                raise httpx.HTTPStatusError(
                    f"Codex API error: {error_detail}",
                    request=response.request,
                    response=response,
                )

            # 스트리밍 응답 수집
            text_content = ""
            reasoning_summary = ""
            model_name = self.model_name
            usage = {}

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                        event_type = data.get("type", "")

                        # 텍스트 응답 수집
                        if event_type == "response.output_text.delta":
                            text_content += data.get("delta", "")

                        # reasoning summary 수집
                        if event_type == "response.reasoning_summary_text.delta":
                            reasoning_summary += data.get("delta", "")

                        # 완료 이벤트에서 모델명, 사용량 추출
                        if event_type == "response.completed":
                            resp_data = data.get("response", {})
                            model_name = resp_data.get("model", self.model_name)
                            usage = resp_data.get("usage", {})

                    except json.JSONDecodeError:
                        pass

            # Chat Completions 형식으로 정규화
            return {
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": text_content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": usage,
                "model": model_name,
                "reasoning_summary": reasoning_summary,
            }

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
            user_message += f"\n\n이전 라운드 컨텍스트:\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self._call_api(messages)
        content = response["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("OpenAI analyze: JSON parse failed, returning raw content")
            return {
                "analysis": content,
                "conclusion": "",
                "confidence": 0.5,
                "key_points": [],
            }

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
{peer_analysis}

본인 분석:
{own_analysis}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self._call_api(messages)
        content = response["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("OpenAI review: JSON parse failed, returning raw content")
            return {
                "feedback": content,
                "agreement_points": [],
                "disagreement_points": [],
            }

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
            [f"모델 {i+1}:\n{view}" for i, view in enumerate(opposing_views)]
        )

        user_message = f"""태스크: {task}

본인 입장:
{own_position}

상대 견해들:
{opposing_views_str}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self._call_api(messages)
        content = response["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("OpenAI debate: JSON parse failed, returning raw content")
            return {
                "updated_position": {
                    "conclusion": content,
                    "confidence": 0.5,
                    "key_points": [],
                },
                "rebuttals": [],
                "concessions": [],
            }
