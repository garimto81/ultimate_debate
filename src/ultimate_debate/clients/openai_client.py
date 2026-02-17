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
from ai_auth import AuthToken, RetryLimitExceededError, TokenStore
from ai_auth.providers import OpenAIProvider

from ultimate_debate.clients.base import BaseAIClient

logger = logging.getLogger(__name__)


class OpenAIClient(BaseAIClient):
    """OpenAI GPT 클라이언트

    ChatGPT Plus/Pro 구독자 전용.
    Browser OAuth로 인증하여 Codex 전용 모델 접근.
    로그인 시 Codex API를 프로빙하여 사용 가능한 최고 성능 모델을 자동 선택합니다.

    중요: ChatGPT 계정은 표준 모델명(o3, gpt-4o 등)이 아닌
    Codex 전용 모델명(gpt-5.3-codex 등)만 사용 가능합니다.

    Codex CLI 호환 엔드포인트 사용:
    - chatgpt.com/backend-api/codex/responses (구독 기반)

    Example:
        client = OpenAIClient()
        await client.ensure_authenticated()  # 프로빙 후 최고 모델 선택
        print(client.model_name)  # e.g. "gpt-5.3-codex"
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

    # Codex 전용 모델 랭킹 (높을수록 우수)
    # ChatGPT Plus/Pro 계정은 Codex 전용 모델명만 사용 가능
    # 표준 모델명(o3, gpt-4o 등)은 Codex API에서 차단됨
    MODEL_CAPABILITY_RANKINGS: dict[str, int] = {
        "gpt-5.3-codex": 100,
        "gpt-5.2-codex": 90,
        "gpt-5.1-codex": 80,
        "gpt-5-codex": 75,
    }

    def __init__(
        self,
        model_name: str = "gpt-5.3-codex",
        token_store: TokenStore | None = None,
    ):
        super().__init__(model_name)
        self.token_store = token_store or TokenStore()
        self.provider = OpenAIProvider()
        self._token: AuthToken | None = None
        self._auth_retry_count = 0  # 재인증 재시도 카운터
        self._max_auth_retries = 1  # 최대 재시도 횟수

        # 모델 발견 결과
        self.discovered_models: list[str] = []

    async def ensure_authenticated(self) -> bool:
        """인증 상태 확인 및 필요시 로그인 + 최적 모델 자동 선택.

        인증 완료 후 Codex API를 프로빙하여
        사용 가능한 최고 성능 모델을 자동 선택합니다.

        Returns:
            bool: 인증 성공 여부
        """
        # 저장된 토큰 확인
        self._token = await self.token_store.load("openai")

        if self._token:
            # 토큰 유효성 확인
            if not self._token.is_expired():
                await self._auto_select_best_model()
                return True

            # 만료된 경우 갱신 시도
            if self._token.refresh_token:
                try:
                    self._token = await self.provider.refresh(self._token)
                    await self.token_store.save(self._token)
                    await self._auto_select_best_model()
                    return True
                except ValueError:
                    pass  # 갱신 실패, 재로그인 필요

        # 새 로그인
        self._token = await self.provider.login()
        await self.token_store.save(self._token)
        await self._auto_select_best_model()
        return True

    async def _auto_select_best_model(self) -> None:
        """Codex API를 프로빙하여 최고 성능 모델 자동 선택."""
        self.discovered_models = await self._discover_models()
        if self.discovered_models:
            best = self._select_best_model(self.discovered_models)
            if best != self.model_name:
                logger.info(f"Model auto-selected: {self.model_name} -> {best}")
                self.model_name = best

    async def _discover_models(self) -> list[str]:
        """Codex API를 프로빙하여 사용 가능한 모델 목록 발견.

        랭킹 순으로 후보 모델에 최소 요청을 보내 가용성을 확인합니다.
        첫 번째 성공 모델을 찾으면 즉시 반환합니다 (최고 성능 우선).

        Returns:
            사용 가능한 모델 이름 리스트
        """
        available = []
        candidates = sorted(
            self.MODEL_CAPABILITY_RANKINGS.keys(),
            key=lambda m: self.MODEL_CAPABILITY_RANKINGS[m],
            reverse=True,
        )

        for model_name in candidates:
            try:
                payload = {
                    "model": model_name,
                    "instructions": "test",
                    "input": [{"role": "user", "content": "hi"}],
                    "stream": True,
                    "store": False,
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{self.CODEX_API_BASE}/responses",
                        headers={
                            "Authorization": f"Bearer {self._token.access_token}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=10.0,
                    )
                    if resp.status_code == 200:
                        available.append(model_name)
                        logger.info(f"Codex model available: {model_name}")
                        break  # 최고 랭킹 모델 발견 즉시 종료
            except Exception:
                continue

        if available:
            logger.info(f"Discovered OpenAI model: {available[0]}")
        else:
            logger.warning("No Codex models available via probing")

        return available

    def _select_best_model(self, available_models: list[str]) -> str:
        """가용 모델 중 최고 성능 모델 선택.

        Args:
            available_models: 사용 가능한 모델 이름 리스트

        Returns:
            최고 랭킹 모델 이름 (없으면 현재 model_name)
        """
        if not available_models:
            return self.model_name

        ranked = sorted(
            available_models,
            key=lambda m: self.MODEL_CAPABILITY_RANKINGS.get(m, 0),
            reverse=True,
        )
        return ranked[0]

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
        system_prompt = """You are an expert technical analyst participating \
in a multi-AI debate.
Analyze the given task thoroughly and provide your independent assessment.

IMPORTANT: Respond ONLY with valid JSON (no markdown, no code blocks).

Response format:
{
    "analysis": "Detailed analysis with specific reasoning",
    "conclusion": "Core conclusion in one clear sentence",
    "confidence": 0.0-1.0,
    "key_points": ["point 1", "point 2"],
    "suggested_steps": ["step 1", "step 2"]
}"""

        user_message = f"Task: {task}"
        if context:
            user_message += f"\n\nPrevious context:\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self._call_api(messages, temperature=0.3)
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
        system_prompt = """Review another AI's analysis and provide \
constructive feedback.
Clearly distinguish between points of agreement and disagreement.

IMPORTANT: Respond ONLY with valid JSON (no markdown, no code blocks).

Response format:
{
    "feedback": "Overall feedback",
    "agreement_points": ["agreement 1", "agreement 2"],
    "disagreement_points": ["disagreement 1: reason", "disagreement 2: reason"],
    "suggested_improvements": ["suggestion 1", "suggestion 2"]
}"""

        # peer_analysis를 읽기 좋게 변환
        peer_summary = (
            f"Conclusion: {peer_analysis.get('conclusion', 'N/A')}\n"
            f"Key Points: {', '.join(peer_analysis.get('key_points', []))}\n"
            f"Confidence: {peer_analysis.get('confidence', 'N/A')}"
        )

        user_message = f"""Task: {task}

Peer Analysis:
{peer_summary}

Your Analysis:
Conclusion: {own_analysis.get('conclusion', 'N/A')}
Key Points: {', '.join(own_analysis.get('key_points', []))}
Confidence: {own_analysis.get('confidence', 'N/A')}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self._call_api(messages, temperature=0.3)
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
        system_prompt = """Participate in debate to refine your position.
Distinguish between rebuttals and concessions to opposing views.

IMPORTANT: Respond ONLY with valid JSON (no markdown, no code blocks).

Response format:
{
    "updated_position": {
        "conclusion": "Updated conclusion",
        "confidence": 0.0-1.0,
        "key_points": ["key points"]
    },
    "rebuttals": ["rebuttal 1", "rebuttal 2"],
    "concessions": ["concession 1: reason", "concession 2: reason"],
    "remaining_disagreements": ["disagreement 1"]
}"""

        # opposing_views를 읽기 좋게 포맷팅
        opposing_views_str = "\n\n".join([
            f"Model {i+1}:\n"
            f"Conclusion: {view.get('conclusion', 'N/A')}\n"
            f"Confidence: {view.get('confidence', 'N/A')}"
            for i, view in enumerate(opposing_views)
        ])

        user_message = f"""Task: {task}

Your Position:
Conclusion: {own_position.get('conclusion', 'N/A')}
Confidence: {own_position.get('confidence', 'N/A')}

Opposing Views:
{opposing_views_str}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self._call_api(messages, temperature=0.3)
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
