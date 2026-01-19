"""OpenAI Client for Ultimate Debate

ChatGPT Plus/Pro 구독자용 AI 클라이언트.
Browser OAuth 인증과 연동.
"""

from typing import Any, Optional

import httpx

from ultimate_debate.clients.base import BaseAIClient
from ultimate_debate.auth import TokenStore, AuthToken
from ultimate_debate.auth.providers import OpenAIProvider


class OpenAIClient(BaseAIClient):
    """OpenAI GPT 클라이언트

    ChatGPT Plus/Pro 구독자 전용.
    Browser OAuth로 인증하여 GPT-4/GPT-5 모델 접근.

    Example:
        client = OpenAIClient(model_name="gpt-4o")
        await client.ensure_authenticated()
        result = await client.analyze("코드 리뷰 요청", context)
    """

    API_BASE = "https://api.openai.com/v1"

    def __init__(
        self, model_name: str = "gpt-4o", token_store: Optional[TokenStore] = None
    ):
        super().__init__(model_name)
        self.token_store = token_store or TokenStore()
        self.provider = OpenAIProvider()
        self._token: Optional[AuthToken] = None

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
        """OpenAI API 호출

        Args:
            messages: 메시지 배열
            temperature: 창의성 조절 (0.0~2.0)
            max_tokens: 최대 토큰 수

        Returns:
            dict: API 응답
        """
        if not self._token:
            await self.ensure_authenticated()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._token.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
                timeout=120.0,
            )

            if response.status_code == 401:
                # 토큰 만료, 재인증 시도
                await self.ensure_authenticated()
                return await self._call_api(messages, temperature, max_tokens)

            response.raise_for_status()
            return response.json()

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
        import json

        return json.loads(response["choices"][0]["message"]["content"])

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
        import json

        return json.loads(response["choices"][0]["message"]["content"])

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
        import json

        return json.loads(response["choices"][0]["message"]["content"])
