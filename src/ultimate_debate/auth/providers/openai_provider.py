"""OpenAI Provider

ChatGPT Plus/Pro 구독자용 Browser OAuth 인증.
Browser OAuth (PKCE) 사용.
"""

import logging
from datetime import datetime, timedelta

import httpx

from ultimate_debate.auth.flows.browser_oauth import (
    BrowserOAuth,
    OAuthCallbackError,
    OAuthConfig,
    generate_pkce_challenge,
)
from ultimate_debate.auth.providers.base import AuthToken, BaseProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI Browser OAuth Provider.

    ChatGPT Plus/Pro 구독자 전용.
    Browser OAuth (PKCE) 사용.

    Example:
        provider = OpenAIProvider()
        token = await provider.login()
    """

    # OpenAI OAuth 설정 (Codex CLI 호환)
    AUTHORIZATION_ENDPOINT = "https://auth.openai.com/oauth/authorize"
    TOKEN_ENDPOINT = "https://auth.openai.com/oauth/token"
    # Codex CLI의 실제 Client ID
    CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
    SCOPE = "openid profile email offline_access"
    # Codex CLI는 고정 포트 1455 사용
    REDIRECT_PORT = 1455

    def __init__(self, client_id: str | None = None):
        """초기화.

        Args:
            client_id: OAuth Client ID (기본값: ChatGPT Web)
        """
        self.client_id = client_id or self.CLIENT_ID
        self._pkce = None
        self._state = None
        self._redirect_uri = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI (ChatGPT Plus/Pro)"

    def get_auth_url(self) -> str:
        """인증 URL 생성 (Step 1).

        Returns:
            str: 브라우저에서 열어야 할 인증 URL
        """
        import secrets
        from urllib.parse import urlencode

        # PKCE 챌린지 생성
        self._pkce = generate_pkce_challenge()
        self._state = secrets.token_urlsafe(32)
        self._redirect_uri = f"http://localhost:{self.REDIRECT_PORT}/auth/callback"

        params = {
            "client_id": self.client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": self.SCOPE,
            "state": self._state,
            "code_challenge": self._pkce.code_challenge,
            "code_challenge_method": self._pkce.code_challenge_method,
        }

        return f"{self.AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    async def exchange_code(self, callback_url: str) -> AuthToken:
        """콜백 URL로 토큰 교환 (Step 2).

        Args:
            callback_url: 브라우저에서 리디렉션된 URL

        Returns:
            AuthToken: 인증 토큰
        """
        from urllib.parse import parse_qs, urlparse

        # URL 파싱
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)

        if "error" in params:
            error_desc = params.get("error_description", ["인증 거부됨"])[0]
            raise ValueError(f"인증 실패: {error_desc}")

        if "code" not in params:
            raise ValueError("URL에서 code 파라미터를 찾을 수 없습니다.")

        code = params["code"][0]

        # 토큰 교환
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_ENDPOINT,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                    "code_verifier": self._pkce.code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                raise ValueError(f"토큰 교환 실패: {response.text}")

            result = response.json()

        expires_at = datetime.now() + timedelta(seconds=result.get("expires_in", 3600))

        return AuthToken(
            provider=self.name,
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
            expires_at=expires_at,
            token_type=result.get("token_type", "Bearer"),
            scopes=result.get("scope", "").split() if result.get("scope") else [],
        )

    def _try_codex_cli_token(self) -> AuthToken | None:
        """Codex CLI의 저장된 토큰 재사용 시도.

        Returns:
            AuthToken | None: 유효한 토큰 또는 None
        """
        import base64
        import json
        from pathlib import Path

        codex_path = Path.home() / ".codex" / "auth.json"
        if not codex_path.exists():
            return None

        try:
            codex = json.loads(codex_path.read_text())
            tokens = codex.get("tokens", {})
            access_token = tokens.get("access_token")
            if not access_token:
                return None

            # JWT exp 추출
            payload_b64 = access_token.split(".")[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))

            exp_dt = datetime.fromtimestamp(payload["exp"])
            if datetime.now() >= exp_dt:
                return None

            profile = payload.get("https://api.openai.com/profile", {})
            auth_info = payload.get("https://api.openai.com/auth", {})

            logger.info("Codex CLI 토큰 재사용")
            return AuthToken(
                provider=self.name,
                access_token=access_token,
                refresh_token=tokens.get("refresh_token"),
                expires_at=exp_dt,
                token_type="Bearer",
                scopes=["openid", "profile", "email", "offline_access"],
                account_info={
                    "email": profile.get("email", ""),
                    "plan_type": auth_info.get("chatgpt_plan_type", ""),
                    "user_id": auth_info.get("chatgpt_user_id", ""),
                    "account_id": auth_info.get(
                        "chatgpt_account_id", ""
                    ),
                },
            )
        except Exception:
            logger.debug("Codex CLI 토큰 읽기 실패")
            return None

    async def login(
        self,
        manual_mode: bool = False,
        **kwargs,
    ) -> AuthToken:
        """Browser OAuth로 로그인.

        Codex CLI 토큰이 있으면 자동 재사용합니다.

        Args:
            manual_mode: True면 수동 URL 입력 모드 사용

        Returns:
            AuthToken: 인증 토큰

        Raises:
            ValueError: OAuth 인증 실패 시
        """
        # Codex CLI 토큰 재사용 시도
        codex_token = self._try_codex_cli_token()
        if codex_token:
            return codex_token

        from rich.console import Console

        console = Console()

        # Browser OAuth (자동 콜백 + 수동 모드 지원)
        # Codex CLI와 동일한 추가 파라미터 사용
        config = OAuthConfig(
            client_id=self.client_id,
            authorization_endpoint=self.AUTHORIZATION_ENDPOINT,
            token_endpoint=self.TOKEN_ENDPOINT,
            redirect_uri="http://localhost:{port}/auth/callback",
            scope=self.SCOPE,
            extra_params={
                "id_token_add_organizations": "true",
                "codex_cli_simplified_flow": "true",
                "originator": "codex_cli_rs",
            },
        )

        oauth = BrowserOAuth(
            config, fixed_port=self.REDIRECT_PORT, manual_callback=manual_mode
        )

        try:
            console.print("[dim]Browser OAuth 시작...[/dim]")
            token_response = await oauth.authenticate(timeout=300)  # 5분 타임아웃
        except OAuthCallbackError as e:
            raise ValueError(f"OpenAI 인증 실패: {e}") from e

        # 만료 시간 계산
        expires_at = datetime.now() + timedelta(seconds=token_response.expires_in)

        return AuthToken(
            provider=self.name,
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            expires_at=expires_at,
            token_type=token_response.token_type,
            scopes=token_response.scope.split() if token_response.scope else [],
        )

    async def refresh(self, token: AuthToken) -> AuthToken:
        """Refresh token으로 갱신.

        Args:
            token: 기존 토큰

        Returns:
            AuthToken: 새 토큰
        """
        if not token.refresh_token:
            raise ValueError("Refresh token이 없습니다. 다시 로그인하세요.")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_ENDPOINT,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token.refresh_token,
                    "client_id": self.client_id,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                raise ValueError(f"토큰 갱신 실패: {response.text}")

            data = response.json()
            expires_in = data.get("expires_in", 3600)
            expires_at = datetime.now() + timedelta(seconds=expires_in)

            scope_str = data.get("scope", "")
            scopes = scope_str.split() if scope_str else token.scopes

            return AuthToken(
                provider=self.name,
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", token.refresh_token),
                expires_at=expires_at,
                token_type=data.get("token_type", "Bearer"),
                scopes=scopes,
            )

    async def logout(self, token: AuthToken) -> bool:
        """로그아웃 (토큰 폐기).

        Args:
            token: 폐기할 토큰

        Returns:
            bool: 성공 여부
        """
        # OpenAI는 로컬에서만 삭제
        return True

    async def validate(self, token: AuthToken) -> bool:
        """토큰 유효성 검증.

        Args:
            token: 검증할 토큰

        Returns:
            bool: 유효 여부
        """
        if token.is_expired():
            return False

        # UserInfo 엔드포인트로 검증 (OAuth 토큰 호환)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://auth.openai.com/userinfo",
                headers={"Authorization": f"Bearer {token.access_token}"},
            )
            return response.status_code == 200

    async def get_account_info(self, token: AuthToken) -> dict | None:
        """계정 정보 조회.

        Args:
            token: 인증 토큰

        Returns:
            dict: 계정 정보 또는 None
        """
        async with httpx.AsyncClient() as client:
            # UserInfo 엔드포인트
            response = await client.get(
                "https://auth.openai.com/userinfo",
                headers={"Authorization": f"Bearer {token.access_token}"},
            )
            if response.status_code == 200:
                try:
                    return response.json()
                except Exception:
                    return None
        return None
