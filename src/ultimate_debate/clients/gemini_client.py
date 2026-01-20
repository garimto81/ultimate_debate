"""Gemini Client for Ultimate Debate

Google Gemini API 클라이언트.
Browser OAuth 인증과 연동.

지원 엔드포인트:
1. Code Assist (cloudcode-pa.googleapis.com) - 기본값, 설정 불필요
2. Vertex AI (GOOGLE_CLOUD_PROJECT 설정 시)
3. Google AI (x-goog-user-project 헤더 사용)
"""

import os
from typing import Any

import httpx

from ultimate_debate.auth import AuthToken, TokenStore
from ultimate_debate.auth.providers import GoogleProvider
from ultimate_debate.clients.base import BaseAIClient


class GeminiClient(BaseAIClient):
    """Google Gemini 클라이언트

    cloud-platform 스코프의 OAuth 토큰으로 Gemini 모델에 접근합니다.

    지원 모드:
    1. Code Assist: cloudcode-pa.googleapis.com 사용 (기본값, 설정 불필요)
    2. Vertex AI: GOOGLE_CLOUD_PROJECT 환경변수 설정 시
    3. Google AI: x-goog-user-project 헤더 사용

    Example:
        # Code Assist 모드 (기본값, 설정 불필요!)
        client = GeminiClient(model_name="gemini-2.0-flash")
        await client.ensure_authenticated()
        result = await client.analyze("코드 리뷰 요청", context)

        # Vertex AI 모드 (프로젝트 ID 필요)
        client = GeminiClient(
            model_name="gemini-2.0-flash",
            project_id="my-gcp-project",
            use_code_assist=False,
            use_vertex_ai=True
        )

    Note:
        Code Assist 모드는 Gemini CLI와 동일한 방식으로 작동합니다.
        프로젝트 ID 자동 발견으로 추가 설정이 필요 없습니다.
    """

    # Code Assist 엔드포인트 (Gemini CLI와 동일)
    CODE_ASSIST_BASE = "https://cloudcode-pa.googleapis.com/v1internal"
    # Google AI 엔드포인트 (x-goog-user-project 헤더 필요)
    GOOGLE_AI_BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        model_name: str = "gemini-2.0-flash",
        token_store: TokenStore | None = None,
        project_id: str | None = None,
        location: str = "us-central1",
        use_code_assist: bool = True,
        use_vertex_ai: bool = False,
    ):
        super().__init__(model_name)
        self.token_store = token_store or TokenStore()
        self.provider = GoogleProvider()
        self._token: AuthToken | None = None
        self._discovered_project_id: str | None = None

        # 프로젝트 설정
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location
        self.use_code_assist = use_code_assist
        self.use_vertex_ai = use_vertex_ai

        # Vertex AI 모델명 매핑 (일반 모델명 → Vertex AI 모델명)
        self._vertex_model_map = {
            "gemini-2.0-flash": "gemini-2.0-flash-001",
            "gemini-2.0-pro": "gemini-2.0-pro-001",
            "gemini-1.5-flash": "gemini-1.5-flash-002",
            "gemini-1.5-pro": "gemini-1.5-pro-002",
        }

        # Code Assist 모델명 매핑 (models/ 접두사 없이)
        self._code_assist_model_map = {
            "gemini-2.0-flash": "gemini-2.0-flash",
            "gemini-2.0-pro": "gemini-2.0-pro",
            "gemini-1.5-flash": "gemini-1.5-flash",
            "gemini-1.5-pro": "gemini-1.5-pro",
        }

    @property
    def vertex_model_name(self) -> str:
        """Vertex AI용 모델 이름 반환"""
        return self._vertex_model_map.get(self.model_name, self.model_name)

    @property
    def code_assist_model_name(self) -> str:
        """Code Assist용 모델 이름 반환"""
        return self._code_assist_model_map.get(
            self.model_name, f"models/{self.model_name}"
        )

    def get_api_endpoint(self) -> str:
        """API 엔드포인트 URL 반환

        Returns:
            str: generateContent 엔드포인트 URL

        Raises:
            ValueError: project_id가 설정되지 않은 경우 (Vertex AI/Google AI 모드)
        """
        if self.use_code_assist:
            # Code Assist 엔드포인트 (프로젝트 ID 불필요)
            return f"{self.CODE_ASSIST_BASE}:generateContent"

        if not self.project_id:
            raise ValueError(
                "Gemini API 사용을 위해 Google Cloud 프로젝트 ID가 필요합니다.\n"
                "다음 중 하나를 설정하세요:\n"
                "  1. 환경변수: GOOGLE_CLOUD_PROJECT=your-project-id\n"
                "  2. 생성자 인자: GeminiClient(project_id='your-project-id')\n"
                "  3. Code Assist 모드 사용: GeminiClient(use_code_assist=True)"
            )

        if self.use_vertex_ai:
            # Vertex AI 엔드포인트
            return (
                f"https://{self.location}-aiplatform.googleapis.com/v1/"
                f"projects/{self.project_id}/locations/{self.location}/"
                f"publishers/google/models/{self.vertex_model_name}:generateContent"
            )
        else:
            # Google AI 엔드포인트
            return f"{self.GOOGLE_AI_BASE}/models/{self.model_name}:generateContent"

    def _get_headers(self) -> dict[str, str]:
        """API 요청 헤더 반환"""
        headers = {
            "Authorization": f"Bearer {self._token.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Code Assist 모드: Gemini CLI 호환 User-Agent 사용
        if self.use_code_assist:
            headers["User-Agent"] = "ultimate-debate/1.0.0"
        # Google AI 모드에서는 x-goog-user-project 헤더 필요
        elif not self.use_vertex_ai and self.project_id:
            headers["x-goog-user-project"] = self.project_id

        return headers

    async def ensure_authenticated(self) -> bool:
        """인증 상태 확인 및 필요시 로그인

        Returns:
            bool: 인증 성공 여부
        """
        # 저장된 토큰 확인
        self._token = await self.token_store.load("google")

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

    def _build_request_body(
        self, contents: list[dict], temperature: float = 0.7, max_tokens: int = 4096
    ) -> dict:
        """API 요청 본문 생성

        Args:
            contents: 콘텐츠 배열
            temperature: 창의성 조절 (0.0~2.0)
            max_tokens: 최대 토큰 수

        Returns:
            dict: 요청 본문
        """
        if self.use_code_assist:
            # Code Assist API는 request 래퍼와 model 필드 필요
            # responseMimeType은 Code Assist에서 미지원
            return {
                "model": self.code_assist_model_name,
                "request": {
                    "contents": contents,
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens,
                    },
                },
            }
        else:
            # Vertex AI / Google AI 형식
            generation_config = {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            }
            return {
                "contents": contents,
                "generationConfig": generation_config,
            }

    async def _call_api(
        self, contents: list[dict], temperature: float = 0.7, max_tokens: int = 4096
    ) -> dict:
        """Gemini API 호출

        Args:
            contents: 콘텐츠 배열
            temperature: 창의성 조절 (0.0~2.0)
            max_tokens: 최대 토큰 수

        Returns:
            dict: API 응답

        Raises:
            ValueError: project_id가 설정되지 않은 경우
            PermissionError: API 권한 오류
        """
        if not self._token:
            await self.ensure_authenticated()

        endpoint_url = self.get_api_endpoint()
        headers = self._get_headers()
        request_body = self._build_request_body(contents, temperature, max_tokens)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint_url,
                headers=headers,
                json=request_body,
                timeout=120.0,
            )

            if response.status_code == 401:
                # 토큰 만료, 재인증 시도
                await self.ensure_authenticated()
                return await self._call_api(contents, temperature, max_tokens)

            if response.status_code == 403:
                # 권한 오류 - 상세 메시지 제공
                try:
                    error_detail = response.json().get("error", {}).get("message", "")
                except Exception:
                    error_detail = response.text

                if self.use_code_assist:
                    raise PermissionError(
                        f"Code Assist API 권한 오류: {error_detail}\n\n"
                        f"해결 방법:\n"
                        f"  1. /ai-login google 으로 재로그인\n"
                        f"  2. Google 계정에 Gemini 접근 권한 확인\n"
                        f"  3. 또는 Vertex AI 모드 사용: use_code_assist=False, "
                        f"use_vertex_ai=True"
                    )
                elif self.use_vertex_ai:
                    api_url = (
                        "https://console.cloud.google.com/apis/library/"
                        "aiplatform.googleapis.com"
                    )
                    raise PermissionError(
                        f"Vertex AI API 권한 오류: {error_detail}\n\n"
                        f"해결 방법:\n"
                        f"  1. 프로젝트 '{self.project_id}'에서 "
                        f"Vertex AI API 활성화\n"
                        f"     {api_url}\n"
                        f"  2. 또는 Code Assist 모드 사용: use_code_assist=True"
                    )
                else:
                    api_url = (
                        "https://console.cloud.google.com/apis/library/"
                        "generativelanguage.googleapis.com"
                    )
                    raise PermissionError(
                        f"Google AI API 권한 오류: {error_detail}\n\n"
                        f"해결 방법:\n"
                        f"  1. 프로젝트 '{self.project_id}'에서 "
                        f"Generative Language API 활성화\n"
                        f"     {api_url}\n"
                        f"  2. 또는 Code Assist 모드 사용: use_code_assist=True"
                    )

            response.raise_for_status()
            return response.json()

    def _extract_text(self, response: dict) -> str:
        """응답에서 텍스트 추출"""
        try:
            return response["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return ""

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

        contents = [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]}
        ]

        response = await self._call_api(contents)
        import json

        return json.loads(self._extract_text(response))

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

        contents = [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]}
        ]

        response = await self._call_api(contents)
        import json

        return json.loads(self._extract_text(response))

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

        contents = [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]}
        ]

        response = await self._call_api(contents)
        import json

        return json.loads(self._extract_text(response))
