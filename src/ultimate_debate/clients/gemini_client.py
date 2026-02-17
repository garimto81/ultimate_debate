"""Gemini Client for Ultimate Debate

Google Gemini API 클라이언트.
Browser OAuth 인증과 연동.

지원 엔드포인트:
1. Code Assist (cloudcode-pa.googleapis.com) - 기본값, 설정 불필요
2. Vertex AI (GOOGLE_CLOUD_PROJECT 설정 시)
3. Google AI (x-goog-user-project 헤더 사용)
"""

import json
import logging
import os
import re
import uuid
from typing import Any

import httpx
from ai_auth import AuthToken, RetryLimitExceededError, TokenStore
from ai_auth.providers import GoogleProvider

from ultimate_debate.clients.base import BaseAIClient

logger = logging.getLogger(__name__)


class GeminiClient(BaseAIClient):
    """Google Gemini 클라이언트

    cloud-platform 스코프의 OAuth 토큰으로 Gemini 모델에 접근합니다.
    로그인 시 Google AI API에서 모델 리스트를 조회하여 최고 성능 모델을 자동 선택합니다.

    지원 모드:
    1. Code Assist: cloudcode-pa.googleapis.com 사용 (기본값, 설정 불필요)
    2. Vertex AI: GOOGLE_CLOUD_PROJECT 환경변수 설정 시
    3. Google AI: x-goog-user-project 헤더 사용

    Example:
        # 자동 모델 선택 (기본값 - 최고 성능 모델 자동 발견)
        client = GeminiClient()
        await client.ensure_authenticated()  # 모델 리스트 조회 + 최고 모델 선택
        print(client.model_name)  # e.g. "gemini-2.5-pro"

        # 수동 모델 지정 (자동 선택 비활성화)
        client = GeminiClient(model_name="gemini-2.5-flash")
        await client.ensure_authenticated()

    Note:
        Code Assist 모드는 Gemini CLI와 동일한 방식으로 작동합니다.
        프로젝트 ID 자동 발견으로 추가 설정이 필요 없습니다.
    """

    # Code Assist 엔드포인트 (Gemini CLI와 동일)
    CODE_ASSIST_BASE = "https://cloudcode-pa.googleapis.com/v1internal"
    # Google AI 엔드포인트 (x-goog-user-project 헤더 필요)
    GOOGLE_AI_BASE = "https://generativelanguage.googleapis.com/v1beta"

    # 모델 성능 랭킹 (높을수록 우수) - API 조회 후 필터링에 사용
    MODEL_CAPABILITY_RANKINGS: dict[str, int] = {
        "gemini-2.5-pro": 100,
        "gemini-2.5-flash": 80,
        "gemini-2.0-pro": 70,
        "gemini-2.0-flash": 60,
        "gemini-1.5-pro": 50,
        "gemini-1.5-flash": 40,
    }

    def __init__(
        self,
        model_name: str = "gemini-2.5-pro",
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
        self._session_id: str = str(uuid.uuid4())
        self._auth_retry_count = 0  # 재인증 재시도 카운터
        self._max_auth_retries = 1  # 최대 재시도 횟수

        # 모델 발견 결과
        self.discovered_models: list[str] = []

        # 프로젝트 설정
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location
        self.use_code_assist = use_code_assist
        self.use_vertex_ai = use_vertex_ai

        # Vertex AI 모델명 매핑 (일반 모델명 → Vertex AI 모델명)
        self._vertex_model_map = {
            "gemini-2.5-pro": "gemini-2.5-pro",
            "gemini-2.5-flash": "gemini-2.5-flash",
            "gemini-2.0-flash": "gemini-2.0-flash-001",
            "gemini-2.0-pro": "gemini-2.0-pro-001",
            "gemini-1.5-flash": "gemini-1.5-flash-002",
            "gemini-1.5-pro": "gemini-1.5-pro-002",
        }

        # Code Assist 모델명 매핑 (models/ 접두사 없이)
        self._code_assist_model_map = {
            "gemini-2.5-pro": "gemini-2.5-pro",
            "gemini-2.5-flash": "gemini-2.5-flash",
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
        """인증 상태 확인 및 필요시 로그인 + 최적 모델 자동 선택.

        인증 완료 후 Google AI API에서 모델 리스트를 조회하여
        generateContent를 지원하는 모델 중 최고 성능 모델을 자동 선택합니다.

        Returns:
            bool: 인증 성공 여부
        """
        # 저장된 토큰 확인
        self._token = await self.token_store.load("google")

        if self._token:
            # 토큰 유효성 확인
            if not self._token.is_expired():
                # Code Assist 모드에서는 project ID 발견 필요
                if self.use_code_assist and not self._discovered_project_id:
                    await self._discover_project_id()
                await self._auto_select_best_model()
                return True

            # 만료된 경우 갱신 시도
            if self._token.refresh_token:
                try:
                    self._token = await self.provider.refresh(self._token)
                    await self.token_store.save(self._token)
                    if self.use_code_assist:
                        await self._discover_project_id()
                    await self._auto_select_best_model()
                    return True
                except ValueError:
                    pass  # 갱신 실패, 재로그인 필요

        # 새 로그인
        self._token = await self.provider.login()
        await self.token_store.save(self._token)
        if self.use_code_assist:
            await self._discover_project_id()
        await self._auto_select_best_model()
        return True

    async def _auto_select_best_model(self) -> None:
        """API에서 모델 리스트를 조회하여 최고 성능 모델 자동 선택."""
        self.discovered_models = await self._discover_models()
        if self.discovered_models:
            best = self._select_best_model(self.discovered_models)
            if best != self.model_name:
                logger.info(f"Model auto-selected: {self.model_name} -> {best}")
                self.model_name = best

    async def _discover_models(self) -> list[str]:
        """Google AI API에서 사용 가능한 Gemini 모델 목록 조회.

        Returns:
            generateContent를 지원하는 모델 이름 리스트
        """
        try:
            headers = {
                "Authorization": f"Bearer {self._token.access_token}",
            }
            if self._discovered_project_id:
                headers["x-goog-user-project"] = self._discovered_project_id

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.GOOGLE_AI_BASE}/models",
                    headers=headers,
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    logger.warning(f"Model list API returned {resp.status_code}")
                    return []

                data = resp.json()
                models = []
                for model in data.get("models", []):
                    name = model.get("name", "").replace("models/", "")
                    methods = model.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        models.append(name)

                logger.info(f"Discovered {len(models)} Gemini models")
                return models

        except Exception as e:
            logger.warning(f"Model discovery failed: {e}")
            return []

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

    async def _discover_project_id(self) -> None:
        """Code Assist API로 project ID 발견 (Gemini CLI 호환).

        loadCodeAssist 엔드포인트를 호출하여 프로젝트 ID를 자동 발견합니다.
        환경변수 GOOGLE_CLOUD_PROJECT가 설정되어 있으면 우선 사용합니다.
        """
        env_project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv(
            "GOOGLE_CLOUD_PROJECT_ID"
        )

        load_url = f"{self.CODE_ASSIST_BASE}:loadCodeAssist"
        headers = {
            "Authorization": f"Bearer {self._token.access_token}",
            "Content-Type": "application/json",
        }
        request_body = {
            "cloudaicompanionProject": env_project,
            "metadata": {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
                "duetProject": env_project,
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    load_url,
                    headers=headers,
                    json=request_body,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

            # 응답에서 project ID 추출
            discovered = data.get("cloudaicompanionProject")
            if discovered:
                self._discovered_project_id = discovered
                logger.info(f"Code Assist project discovered: {discovered}")
            elif env_project:
                self._discovered_project_id = env_project
                logger.info(f"Using env project ID: {env_project}")
            else:
                logger.warning(
                    "No project ID discovered from loadCodeAssist. "
                    "Set GOOGLE_CLOUD_PROJECT env var if API calls fail."
                )
        except Exception as e:
            logger.warning(f"loadCodeAssist failed: {e}")
            if env_project:
                self._discovered_project_id = env_project

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
            # Code Assist API: Gemini CLI 호환 형식
            # project, user_prompt_id, session_id 필수
            return {
                "model": self.code_assist_model_name,
                "project": self._discovered_project_id,
                "user_prompt_id": str(uuid.uuid4()),
                "request": {
                    "contents": contents,
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens,
                    },
                    "session_id": self._session_id,
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
                if self._auth_retry_count >= self._max_auth_retries:
                    raise RetryLimitExceededError(
                        "Authentication failed after retry. "
                        "Please re-login with /ai-login google",
                        max_retries=self._max_auth_retries,
                        attempts=self._auth_retry_count,
                        provider="google"
                    )
                self._auth_retry_count += 1
                await self.ensure_authenticated()
                result = await self._call_api(contents, temperature, max_tokens)
                self._auth_retry_count = 0  # 성공 시 리셋
                return result

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
        """응답에서 텍스트 추출

        Code Assist API는 {"response": {"candidates": [...]}} 형식,
        Vertex AI/Google AI는 {"candidates": [...]} 형식.
        """
        # Code Assist: response 래퍼 안에 candidates
        data = response.get("response", response)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
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

        contents = [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]}
        ]

        response = await self._call_api(contents, temperature=0.3)
        text = self._extract_text(response)
        parsed = self._parse_json_response(text)
        if parsed is not None:
            return parsed
        logger.warning("Gemini analyze: JSON parse failed, returning raw content")
        return {
            "analysis": text,
            "conclusion": "",
            "confidence": 0.5,
            "key_points": [],
        }

    @staticmethod
    def _parse_json_response(text: str) -> dict | None:
        """텍스트에서 JSON 추출 (markdown 코드블록 지원)."""
        # 1차: 직접 파싱
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        # 2차: markdown 코드블록에서 추출
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

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

        contents = [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]}
        ]

        response = await self._call_api(contents, temperature=0.3)
        text = self._extract_text(response)
        parsed = self._parse_json_response(text)
        if parsed is not None:
            return parsed
        logger.warning("Gemini review: JSON parse failed, returning raw content")
        return {
            "feedback": text,
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

        contents = [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]}
        ]

        response = await self._call_api(contents, temperature=0.3)
        text = self._extract_text(response)
        parsed = self._parse_json_response(text)
        if parsed is not None:
            return parsed
        logger.warning("Gemini debate: JSON parse failed, returning raw content")
        return {
            "updated_position": {
                "conclusion": text,
                "confidence": 0.5,
                "key_points": [],
            },
            "rebuttals": [],
            "concessions": [],
        }
