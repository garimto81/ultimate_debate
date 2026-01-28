"""Google Provider

Gemini API용 인증.
- API Key 방식
- Gemini CLI 토큰 재사용
- Browser OAuth 2.0 + PKCE
"""

import json
import os
import socket
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from ultimate_debate.auth.flows.browser_oauth import (
    BrowserOAuth,
    OAuthCallbackError,
    OAuthConfig,
)
from ultimate_debate.auth.providers.base import AuthToken, BaseProvider


def try_import_gemini_cli_token() -> AuthToken | None:
    """Gemini CLI 토큰 재사용 (~/.gemini/oauth_creds.json)

    Gemini CLI가 저장한 OAuth 토큰을 가져와서 재사용합니다.

    Returns:
        AuthToken: 유효한 토큰이 있으면 반환, 없으면 None
    """
    gemini_creds_path = Path.home() / ".gemini" / "oauth_creds.json"

    if not gemini_creds_path.exists():
        return None

    try:
        with open(gemini_creds_path) as f:
            creds = json.load(f)

        access_token = creds.get("access_token")
        refresh_token = creds.get("refresh_token")
        expires_at_str = creds.get("expires_at")

        if not access_token:
            return None

        # expires_at 파싱 (ISO 형식 또는 Unix timestamp)
        expires_at = None
        if expires_at_str:
            if isinstance(expires_at_str, (int, float)):
                expires_at = datetime.fromtimestamp(expires_at_str)
            else:
                # ISO 형식
                expires_at = datetime.fromisoformat(
                    expires_at_str.replace("Z", "+00:00")
                )
                expires_at = expires_at.replace(tzinfo=None)

        # 만료 확인
        if expires_at and expires_at <= datetime.now():
            return None

        return AuthToken(
            provider="google",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            token_type="Bearer",
            scopes=creds.get("scopes", []),
        )
    except Exception:
        return None


class GoogleProvider(BaseProvider):
    """Google Gemini API용 Provider

    OAuth 2.0 Authorization Code + PKCE 사용.
    Browser OAuth 방식으로 인증.

    Gemini CLI의 공개 Client ID를 사용하여
    별도 설정 없이 브라우저 로그인이 가능합니다.

    Example:
        provider = GoogleProvider()
        token = await provider.login()
    """

    # Google OAuth 설정
    AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    # Gemini CLI 공개 Client ID (Code Assist용)
    # 참고: https://github.com/RooCodeInc/Roo-Code/issues/5134
    # Google Cloud SDK Client ID는 generative-language scope 미지원
    DEFAULT_CLIENT_ID = (
        "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
    )
    DEFAULT_CLIENT_SECRET = "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"
    # 기본 스코프 (Gemini Code Assist용)
    # cloud-platform만으로 Gemini API 접근 가능 (Code Assist 경로)
    SCOPE = "https://www.googleapis.com/auth/cloud-platform openid email"
    # 로컬 콜백 포트 설정
    DEFAULT_REDIRECT_PORT = 8080
    MAX_PORT_ATTEMPTS = 10

    # Gemini API 검증 엔드포인트
    GEMINI_MODELS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self, client_id: str | None = None, client_secret: str | None = None
    ):
        # 환경변수 또는 기본 공개 Client ID 사용
        self.client_id = (
            client_id
            or os.getenv("GOOGLE_CLIENT_ID")
            or self.DEFAULT_CLIENT_ID
        )
        self.client_secret = (
            client_secret
            or os.getenv("GOOGLE_CLIENT_SECRET")
            or self.DEFAULT_CLIENT_SECRET
        )

    def _is_port_available(self, port: int) -> bool:
        """포트 사용 가능 여부 확인"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return True
        except OSError:
            return False

    def _find_available_port(
        self, start_port: int = 8080, max_attempts: int = 10
    ) -> int:
        """사용 가능한 포트 찾기

        Args:
            start_port: 시작 포트 번호
            max_attempts: 최대 시도 횟수

        Returns:
            int: 사용 가능한 포트

        Raises:
            RuntimeError: 사용 가능한 포트를 찾지 못한 경우
        """
        for port in range(start_port, start_port + max_attempts):
            if self._is_port_available(port):
                return port
        end_port = start_port + max_attempts - 1
        raise RuntimeError(f"사용 가능한 포트를 찾을 수 없음 ({start_port}-{end_port})")

    @property
    def name(self) -> str:
        return "google"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

    async def login(self, **kwargs) -> AuthToken:
        """Browser OAuth로 로그인

        Gemini CLI 토큰이 있으면 우선 재사용합니다.
        없거나 만료된 경우에만 브라우저 로그인을 진행합니다.

        Gemini CLI의 공개 Client ID를 사용하므로
        별도 설정 없이 바로 로그인 가능합니다.

        동적 포트 할당을 사용하여 포트 충돌을 방지합니다.
        """
        # 1. Gemini CLI 토큰 확인 (우선)
        cli_token = try_import_gemini_cli_token()
        if cli_token and not cli_token.is_expired():
            print("[GoogleProvider] Gemini CLI 토큰 재사용")
            return cli_token

        # 2. CLI 토큰 없거나 만료 시 브라우저 로그인
        # 동적 포트 할당
        port = self._find_available_port(
            self.DEFAULT_REDIRECT_PORT, self.MAX_PORT_ATTEMPTS
        )

        config = OAuthConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            authorization_endpoint=self.AUTHORIZATION_ENDPOINT,
            token_endpoint=self.TOKEN_ENDPOINT,
            redirect_uri=f"http://localhost:{port}/callback",
            scope=self.SCOPE,
        )

        oauth = BrowserOAuth(config, fixed_port=port)

        try:
            token_response = await oauth.authenticate(timeout=300)
        except OAuthCallbackError as e:
            raise ValueError(f"Google 인증 실패: {e}") from e

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

    async def login_with_api_key(self, api_key: str) -> AuthToken:
        """API Key로 인증

        Google AI Studio에서 발급받은 API Key를 사용합니다.
        https://aistudio.google.com/app/apikey

        Args:
            api_key: Google AI Studio API Key

        Returns:
            AuthToken: API Key 토큰 (만료 없음)

        Raises:
            ValueError: API Key가 유효하지 않은 경우
        """
        # API Key 유효성 검증
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GEMINI_MODELS_ENDPOINT,
                params={"key": api_key},
            )

            if response.status_code != 200:
                error_data = response.json().get("error", {})
                error_msg = error_data.get("message", "Unknown error")
                raise ValueError(f"API Key 검증 실패: {error_msg}")

        # API Key를 access_token으로 저장 (만료 없음)
        return AuthToken(
            provider=self.name,
            access_token=api_key,
            refresh_token=None,
            expires_at=None,  # API Key는 만료 없음
            token_type="api_key",  # OAuth와 구분
            scopes=["generative-language"],
        )

    async def refresh(self, token: AuthToken) -> AuthToken:
        """Refresh token으로 갱신"""
        if not token.refresh_token:
            raise ValueError("No refresh token available")

        async with httpx.AsyncClient() as client:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
                "client_id": self.client_id,
            }
            if self.client_secret:
                data["client_secret"] = self.client_secret

            response = await client.post(self.TOKEN_ENDPOINT, data=data)

            if response.status_code != 200:
                raise ValueError(f"Token refresh failed: {response.text}")

            result = response.json()
            expires_at = datetime.now() + timedelta(
                seconds=result.get("expires_in", 3600)
            )

            return AuthToken(
                provider=self.name,
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token", token.refresh_token),
                expires_at=expires_at,
                token_type=result.get("token_type", "Bearer"),
                scopes=(
                    result.get("scope", "").split()
                    if result.get("scope")
                    else token.scopes
                ),
            )

    async def logout(self, token: AuthToken) -> bool:
        """토큰 폐기"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": token.access_token},
            )
            return response.status_code == 200

    async def validate(self, token: AuthToken) -> bool:
        """토큰 유효성 검증"""
        if token.is_expired():
            return False

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"access_token": token.access_token},
            )
            return response.status_code == 200

    async def get_account_info(self, token: AuthToken) -> dict | None:
        """계정 정보 조회"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token.access_token}"},
            )
            if response.status_code == 200:
                return response.json()
        return None
